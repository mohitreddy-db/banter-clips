"""Admin console API — the aggregate + action endpoints behind /admin/**.

Design (ADMIN.md v2): the dashboard is a summary; every widget drills into a
detail endpoint here. Everything is computed live from the tables we already
have (users, clips, jobs, publishes, events, social_accounts, stripe_events)
plus Stripe deep links and the OpenRouter credits API — no analytics product.

Credits are deliberately NOT implemented: /admin/credits reports
``enabled: false`` with the PRICING.md launch price list so the page (and any
future ledger work) has one obvious place to land. Nothing else in this file
assumes credits exist; costs are dollars from clips.cost_usd.

Every mutating endpoint writes an AdminAction row — the audit log is the read
view of those rows, and rows are never edited or deleted from the app.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import distinct, func, or_, select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_admin_user
from ..models import (
    GENERATION_STAGES,
    AdminAction,
    Clip,
    Event,
    Job,
    Publish,
    SocialAccount,
    StripeEvent,
    User,
)
from ..services import jobs as jobsvc
from ..services import provider_balance, runtime_settings, spend, storage
from ..services.generation import start_generation
from ..services.publishing import start_publish

log = logging.getLogger("banter.admin")

router = APIRouter(prefix="/admin", tags=["admin-console"])

CREATOR_PRICE_USD = 9.99
PROCESSING_STATUSES = ("queued", *GENERATION_STAGES, "script_ready")
PAGE_SIZE = 50

# PRICING.md §4 launch price list — surfaced read-only by /admin/credits so
# the constants live in exactly one backend place when the ledger ships.
CREDIT_PRICE_LIST = {
    "video": {"10s": {"720p": 250, "1080p": 425},
              "15s": {"720p": 375, "1080p": 650},
              "30s": {"720p": 700, "1080p": 1200}},
    "extras": {"enhance_take": 2, "captions": 0, "publish": 0, "retry": 0},
    "face_value_usd": 0.01,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: Session, admin: User, action: str, target: str = "", reason: str = "") -> None:
    db.add(AdminAction(admin_email=admin.email, action=action, target=target, reason=reason))


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# --------------------------------------------------------------- overview


@router.get("/overview")
def overview(
    days: int = Query(7, ge=1, le=90),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    now = _now()
    since = now - timedelta(days=days)
    day_ago = now - timedelta(hours=24)

    total_users = db.scalar(select(func.count(User.id))) or 0
    new_users = db.scalar(select(func.count(User.id)).where(User.created_at >= since)) or 0
    active_users = db.scalar(
        select(func.count(distinct(Event.user_id))).where(
            Event.created_at >= since, Event.user_id.is_not(None)
        )
    ) or 0

    total_clips = db.scalar(select(func.count(Clip.id))) or 0
    period_clips = db.scalar(select(func.count(Clip.id)).where(Clip.created_at >= since)) or 0
    ready_clips = db.scalar(select(func.count(Clip.id)).where(Clip.status == "ready")) or 0
    published_clips = db.scalar(
        select(func.count(distinct(Publish.clip_id))).where(Publish.status == "published")
    ) or 0

    paying = db.scalar(select(func.count(User.id)).where(User.plan == "creator")) or 0
    mrr = round(paying * CREATOR_PRICE_USD, 2)

    cost_period = float(db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0)).where(Clip.created_at >= since)
    ) or 0)
    cost_today = float(db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0)).where(Clip.created_at >= day_ago)
    ) or 0)
    cost_30d = float(db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0)).where(
            Clip.created_at >= now - timedelta(days=30)
        )
    ) or 0)
    costed_clips = db.scalar(
        select(func.count(Clip.id)).where(Clip.created_at >= since, Clip.cost_usd.is_not(None))
    ) or 0

    # Margin on a subscription basis until credits ship: MRR vs 30d AI cost.
    margin_pct = round((mrr - cost_30d) / mrr * 100, 1) if mrr > 0 else None

    balance = provider_balance.get()
    daily_cap = runtime_settings.daily_cap(db)
    paused = runtime_settings.generation_paused(db)
    spent_24h = spend.spent_last_day(db)
    beat_at, beat_by = runtime_settings.worker_heartbeat(db)
    worker_alive = beat_at is not None and (now - beat_at).total_seconds() < 90

    # 24h failure rate — the "quality spike" alert input.
    done_24h = db.scalar(select(func.count(Clip.id)).where(
        Clip.completed_at >= day_ago, Clip.status == "ready")) or 0
    failed_24h = db.scalar(select(func.count(Clip.id)).where(
        Clip.created_at >= day_ago, Clip.status == "failed")) or 0
    fail_rate_24h = round(failed_24h / (done_24h + failed_24h) * 100, 1) if (done_24h + failed_24h) else 0.0

    alerts: list[dict] = []
    if paused:
        alerts.append({"level": "error", "message": "Generation is PAUSED (kill switch on).",
                       "link": "/admin/jobs"})
    if balance is not None and balance["balance_usd"] < 20:
        alerts.append({"level": "error",
                       "message": f"OpenRouter balance low — ${balance['balance_usd']:.2f} left. "
                                  "Generation fails at $0.", "link": "/admin/costs"})
    if fail_rate_24h >= 15 and (done_24h + failed_24h) >= 3:
        alerts.append({"level": "warn",
                       "message": f"Failure rate {fail_rate_24h:.0f}% in the last 24h.",
                       "link": "/admin/costs"})
    if daily_cap > 0 and spent_24h >= 0.8 * daily_cap:
        alerts.append({"level": "warn",
                       "message": f"Daily spend ${spent_24h:.2f} is {spent_24h / daily_cap * 100:.0f}% "
                                  f"of the ${daily_cap:.0f} cap.", "link": "/admin/jobs"})
    if not worker_alive:
        alerts.append({"level": "error", "message": "Worker heartbeat missing — queue may be stalled.",
                       "link": "/admin/jobs"})

    # Funnel: signups → first video → 2+ videos → published → paid.
    users_with_clip = db.scalar(select(func.count(distinct(Clip.user_id)))) or 0
    two_plus = db.scalar(select(func.count()).select_from(
        select(Clip.user_id).group_by(Clip.user_id).having(func.count(Clip.id) >= 2).subquery()
    )) or 0
    users_published = db.scalar(
        select(func.count(distinct(Clip.user_id)))
        .select_from(Clip)
        .join(Publish, Publish.clip_id == Clip.id)
        .where(Publish.status == "published")
    ) or 0

    sports_rows = db.execute(
        select(Clip.sport, func.count(Clip.id)).group_by(Clip.sport).order_by(func.count(Clip.id).desc())
    ).all()
    sports_total = sum(n for _, n in sports_rows) or 1

    tone_rows = db.execute(
        select(
            Clip.tone,
            func.count(Clip.id).filter(Clip.status == "ready"),
            func.count(distinct(Publish.clip_id)).filter(Publish.status == "published"),
        )
        .select_from(Clip)
        .outerjoin(Publish, Publish.clip_id == Clip.id)
        .group_by(Clip.tone)
    ).all()

    top_takes = db.execute(
        select(Clip.take, Clip.sport, Clip.tone,
               func.count(Publish.id).filter(Publish.status == "published").label("pubs"))
        .outerjoin(Publish, Publish.clip_id == Clip.id)
        .where(Clip.status == "ready")
        .group_by(Clip.id)
        .order_by(func.count(Publish.id).filter(Publish.status == "published").desc(),
                  Clip.created_at.desc())
        .limit(5)
    ).all()

    return {
        "range_days": days,
        "users": {"total": total_users, "new": new_users, "active": active_users},
        "videos": {"total": total_clips, "period": period_clips, "ready": ready_clips,
                   "published_clips": published_clips,
                   "publish_rate_pct": round(published_clips / ready_clips * 100, 1) if ready_clips else 0.0},
        "revenue": {"mrr": mrr, "paying_users": paying,
                    "conversion_pct": round(paying / total_users * 100, 1) if total_users else 0.0},
        "ai_cost": {"period": round(cost_period, 2), "today": round(cost_today, 2),
                    "cost_per_video": round(cost_period / costed_clips, 2) if costed_clips else None},
        "margin_pct": margin_pct,
        "provider_balance": balance,
        "caps": {"daily_cap": daily_cap, "spent_24h": round(spent_24h, 2), "paused": paused},
        "worker": {"alive": worker_alive, "last_beat": _iso(beat_at), "name": beat_by},
        "alerts": alerts,
        "funnel": [
            {"label": "Signups", "count": total_users},
            {"label": "First video", "count": users_with_clip},
            {"label": "2+ videos", "count": two_plus},
            {"label": "Published", "count": users_published},
            {"label": "Paid", "count": paying},
        ],
        "top_sports": [{"sport": s, "count": n, "pct": round(n / sports_total * 100)}
                       for s, n in sports_rows],
        "tone_publish": [
            {"tone": t, "ready": r, "published": p,
             "rate_pct": round(p / r * 100, 1) if r else 0.0}
            for t, r, p in tone_rows
        ],
        "top_takes": [{"take": t, "sport": s, "tone": tn, "publishes": p}
                      for t, s, tn, p in top_takes],
        "credits_enabled": False,
    }


# ------------------------------------------------------------------ users


@router.get("/users")
def list_users(
    q: str = "",
    plan: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    ev = select(Event.user_id, func.max(Event.created_at).label("last_seen")) \
        .where(Event.user_id.is_not(None)).group_by(Event.user_id).subquery()
    cl = select(Clip.user_id, func.count(Clip.id).label("videos"),
                func.coalesce(func.sum(Clip.cost_usd), 0).label("cost")) \
        .group_by(Clip.user_id).subquery()

    last_active = func.greatest(User.last_login_at, ev.c.last_seen)
    stmt = (
        select(User, ev.c.last_seen, func.coalesce(cl.c.videos, 0), func.coalesce(cl.c.cost, 0))
        .outerjoin(ev, ev.c.user_id == User.id)
        .outerjoin(cl, cl.c.user_id == User.id)
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.display_name.ilike(like)))
    if plan in ("free", "creator"):
        stmt = stmt.where(User.plan == plan)
    if status == "blocked":
        stmt = stmt.where(User.is_blocked.is_(True))
    elif status == "churned":
        stmt = stmt.where(User.cancel_at_period_end.is_(True))
    elif status == "active":
        stmt = stmt.where(User.is_blocked.is_(False))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(last_active.desc().nulls_last(), User.created_at.desc())
        .limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)
    ).all()

    return {
        "total": total, "page": page, "page_size": PAGE_SIZE,
        "users": [
            {
                "id": str(u.id), "email": u.email, "display_name": u.display_name,
                "plan": u.plan, "created_at": _iso(u.created_at),
                "last_active": _iso(max(filter(None, (u.last_login_at, seen)), default=None)),
                "videos": int(videos), "cost_usd": round(float(cost), 2),
                "is_blocked": u.is_blocked,
                "churned": bool(u.cancel_at_period_end),
                "stripe_customer_id": u.stripe_customer_id,
            }
            for u, seen, videos, cost in rows
        ],
    }


@router.get("/users/{user_id}")
def user_detail(user_id: uuid.UUID, admin: User = Depends(get_admin_user),
                db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "No such user")
    clips = db.execute(
        select(Clip).where(Clip.user_id == u.id).order_by(Clip.created_at.desc()).limit(10)
    ).scalars().all()
    publish_count = db.scalar(
        select(func.count(Publish.id)).join(Clip, Clip.id == Publish.clip_id)
        .where(Clip.user_id == u.id, Publish.status == "published")
    ) or 0
    videos = db.scalar(select(func.count(Clip.id)).where(Clip.user_id == u.id)) or 0
    cost = float(db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0)).where(Clip.user_id == u.id)) or 0)
    socials = db.execute(select(SocialAccount).where(SocialAccount.user_id == u.id)).scalars().all()
    return {
        "id": str(u.id), "email": u.email, "display_name": u.display_name, "plan": u.plan,
        "created_at": _iso(u.created_at), "last_login_at": _iso(u.last_login_at),
        "is_blocked": u.is_blocked, "churned": bool(u.cancel_at_period_end),
        "plan_renews_at": _iso(u.plan_renews_at),
        "stripe_customer_id": u.stripe_customer_id,
        "stripe_url": f"https://dashboard.stripe.com/customers/{u.stripe_customer_id}"
        if u.stripe_customer_id else None,
        "videos": videos, "cost_usd": round(cost, 2), "published": publish_count,
        "recent_clips": [
            {"id": str(c.id), "take": c.take, "status": c.status,
             "cost_usd": float(c.cost_usd) if c.cost_usd is not None else None,
             "created_at": _iso(c.created_at)}
            for c in clips
        ],
        "socials": [{"platform": s.platform, "handle": s.handle, "status": s.status,
                     "token_expires_at": _iso(s.token_expires_at)} for s in socials],
    }


class BlockBody(BaseModel):
    blocked: bool
    reason: str = ""


@router.post("/users/{user_id}/block")
def block_user(user_id: uuid.UUID, body: BlockBody,
               admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "No such user")
    if u.id == admin.id:
        raise HTTPException(409, "You cannot block yourself.")
    u.is_blocked = body.blocked
    _audit(db, admin, "block_user" if body.blocked else "unblock_user",
           f"user {u.email}", body.reason)
    db.commit()
    return {"ok": True, "is_blocked": u.is_blocked}


class DeleteUserBody(BaseModel):
    confirm_email: str
    reason: str = ""


@router.post("/users/{user_id}/delete")
def delete_user(user_id: uuid.UUID, body: DeleteUserBody,
                admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Full erasure (the delete-user.py script as a button).

    Typed-email confirmation is enforced server-side too. Stripe subscription
    cancellation is best-effort; the Supabase Auth identity is NOT touched
    (that stays a manual step, as in the script).
    """
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "No such user")
    if body.confirm_email.strip().lower() != (u.email or "").lower():
        raise HTTPException(409, "Confirmation email does not match.")
    if u.id == admin.id:
        raise HTTPException(409, "You cannot delete yourself.")

    # Best-effort: cancel a live Stripe subscription so billing stops.
    if u.stripe_subscription_id and getattr(settings, "STRIPE_SECRET_KEY", ""):
        try:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Subscription.cancel(u.stripe_subscription_id)
        except Exception:  # noqa: BLE001 — finish erasure; Stripe can be cleaned manually
            log.exception("could not cancel Stripe subscription for %s", u.email)

    # Delete stored media for every clip (row cascade will not touch bytes).
    clip_ids = db.execute(select(Clip.id).where(Clip.user_id == u.id)).scalars().all()
    store = storage.get()
    for cid in clip_ids:
        try:
            store.delete_prefix(storage.clip_prefix(u.id, cid))
        except Exception:  # noqa: BLE001
            log.exception("could not remove artifacts for clip %s", cid)

    email = u.email
    db.execute(Event.__table__.delete().where(Event.user_id == u.id))
    db.delete(u)  # cascades: preferences, tokens, clips, publishes, socials
    _audit(db, admin, "delete_user", f"user {email}",
           body.reason or "erasure request")
    db.commit()
    return {"ok": True, "deleted": email, "clips_removed": len(clip_ids)}


# ------------------------------------------------------------ retention


@router.get("/retention")
def retention(weeks: int = Query(5, ge=1, le=12),
              admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Weekly signup cohorts × D1/D7/D14/D30 activity from the events table."""
    now = _now()
    out = []
    for w in range(weeks):
        cohort_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0) - timedelta(weeks=w)
        cohort_end = cohort_start + timedelta(weeks=1)
        member_ids = db.execute(
            select(User.id).where(User.created_at >= cohort_start, User.created_at < cohort_end)
        ).scalars().all()
        size = len(member_ids)
        row = {"cohort": cohort_start.strftime("%b %d"), "size": size}
        for label, day in (("d1", 1), ("d7", 7), ("d14", 14), ("d30", 30)):
            if not size:
                row[label] = None
                continue
            window_start = cohort_start + timedelta(days=day)
            if window_start > now:
                row[label] = None  # cohort too young for this offset
                continue
            active = db.scalar(
                select(func.count(distinct(Event.user_id))).where(
                    Event.user_id.in_(member_ids),
                    Event.created_at >= window_start,
                    Event.created_at < window_start + timedelta(days=7),
                )
            ) or 0
            row[label] = round(active / size * 100)
        out.append(row)
    return {"cohorts": out}


# ------------------------------------------------------------------ videos


def _flagged_condition():
    return or_(
        Clip.error.is_not(None),
        text("jsonb_array_length(coalesce(clips.provenance->'warnings', '[]'::jsonb)) > 0"),
    )


@router.get("/videos")
def list_videos(
    status: str = "",
    sport: str = "",
    q: str = "",
    page: int = Query(1, ge=1),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    published_exists = (
        select(Publish.id).where(Publish.clip_id == Clip.id, Publish.status == "published")
        .exists()
    )
    stmt = select(Clip, User.email, published_exists.label("published")).join(
        User, User.id == Clip.user_id)
    if status == "ready":
        stmt = stmt.where(Clip.status == "ready")
    elif status == "failed":
        stmt = stmt.where(Clip.status == "failed")
    elif status == "processing":
        stmt = stmt.where(Clip.status.in_(PROCESSING_STATUSES))
    elif status == "published":
        stmt = stmt.where(published_exists)
    elif status == "flagged":
        stmt = stmt.where(_flagged_condition())
    if sport:
        stmt = stmt.where(Clip.sport == sport)
    if q:
        stmt = stmt.where(Clip.take.ilike(f"%{q.strip()}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    failed_first = (Clip.status != "failed")  # False sorts first in asc
    rows = db.execute(
        stmt.order_by(failed_first.asc(), Clip.created_at.desc())
        .limit(24).offset((page - 1) * 24)
    ).all()

    def warnings_count(c: Clip) -> int:
        prov = c.provenance or {}
        return len(prov.get("warnings") or [])

    return {
        "total": total, "page": page, "page_size": 24,
        "videos": [
            {
                "id": str(c.id), "take": c.take, "sport": c.sport, "tone": c.tone,
                "status": c.status, "current_step": c.current_step,
                "duration_target": c.duration_target,
                "duration_seconds": float(c.duration_seconds) if c.duration_seconds else None,
                "resolution": c.resolution,
                "cost_usd": float(c.cost_usd) if c.cost_usd is not None else None,
                "user_email": email, "created_at": _iso(c.created_at),
                "thumb_gradient": c.thumb_gradient, "published": bool(published),
                "error": c.error, "warnings": warnings_count(c),
                "is_simulated": c.is_simulated,
            }
            for c, email, published in rows
        ],
    }


@router.get("/videos/{clip_id}")
def video_detail(clip_id: uuid.UUID, admin: User = Depends(get_admin_user),
                 db: Session = Depends(get_db)):
    c = db.get(Clip, clip_id)
    if c is None:
        raise HTTPException(404, "No such clip")
    owner = db.get(User, c.user_id)
    pubs = db.execute(
        select(Publish, SocialAccount.handle)
        .outerjoin(SocialAccount, SocialAccount.id == Publish.social_account_id)
        .where(Publish.clip_id == c.id).order_by(Publish.created_at.desc())
    ).all()
    return {
        "id": str(c.id), "take": c.take, "sport": c.sport, "tone": c.tone,
        "status": c.status, "error": c.error, "current_step": c.current_step,
        "duration_target": c.duration_target,
        "duration_seconds": float(c.duration_seconds) if c.duration_seconds else None,
        "resolution": c.resolution, "watermarked": c.watermarked,
        "cost_usd": float(c.cost_usd) if c.cost_usd is not None else None,
        "created_at": _iso(c.created_at), "completed_at": _iso(c.completed_at),
        "user_email": owner.email if owner else None,
        "user_id": str(c.user_id),
        "video_url": c.video_url, "is_simulated": c.is_simulated,
        "provenance": c.provenance, "script": c.script,
        "script_approved": c.script_approved,
        "publishes": [
            {"id": str(p.id), "status": p.status, "handle": handle, "error": p.error,
             "external_url": p.external_url, "created_at": _iso(p.created_at),
             "published_at": _iso(p.published_at)}
            for p, handle in pubs
        ],
    }


class ReasonBody(BaseModel):
    reason: str = ""


@router.post("/videos/{clip_id}/retry")
def admin_retry_video(clip_id: uuid.UUID, body: ReasonBody = Body(default=ReasonBody()),
                      admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    c = db.get(Clip, clip_id)
    if c is None:
        raise HTTPException(404, "No such clip")
    if c.status != "failed":
        raise HTTPException(409, "Only failed clips can be retried.")
    c.status = "queued"
    c.stage_index = 0
    c.error = None
    _audit(db, admin, "retry_clip", f'clip {str(c.id)[:8]} "{c.take[:40]}"', body.reason)
    db.commit()
    start_generation(c.id)
    return {"ok": True}


@router.post("/videos/{clip_id}/delete")
def admin_delete_video(clip_id: uuid.UUID, body: ReasonBody,
                       admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    c = db.get(Clip, clip_id)
    if c is None:
        raise HTTPException(404, "No such clip")
    try:
        storage.get().delete_prefix(storage.clip_prefix(c.user_id, c.id))
    except Exception:  # noqa: BLE001 — never block a deletion on storage
        log.exception("could not remove artifacts for clip %s", c.id)
    _audit(db, admin, "delete_clip", f'clip {str(c.id)[:8]} "{c.take[:40]}"', body.reason)
    db.delete(c)
    db.commit()
    return {"ok": True}


# -------------------------------------------------------------------- jobs


@router.get("/jobs")
def jobs_view(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    now = _now()
    day_ago = now - timedelta(hours=24)
    depth = jobsvc.depth(db)

    done_24h = db.scalar(select(func.count(Clip.id)).where(
        Clip.completed_at >= day_ago, Clip.status == "ready")) or 0
    failed_24h = db.scalar(select(func.count(Clip.id)).where(
        Clip.created_at >= day_ago, Clip.status == "failed")) or 0
    success_rate = round(done_24h / (done_24h + failed_24h) * 100, 1) \
        if (done_24h + failed_24h) else None
    avg_seconds = db.scalar(
        select(func.avg(func.extract("epoch", Clip.completed_at - Clip.created_at)))
        .where(Clip.completed_at >= day_ago, Clip.status == "ready")
    )
    beat_at, beat_by = runtime_settings.worker_heartbeat(db)
    worker_alive = beat_at is not None and (now - beat_at).total_seconds() < 90

    rows = db.execute(
        select(Job, Clip, User.email)
        .join(Clip, Clip.id == Job.clip_id)
        .join(User, User.id == Clip.user_id)
        .order_by(
            (Job.status != "running").asc(), (Job.status != "queued").asc(),
            Job.created_at.desc(),
        )
        .limit(20)
    ).all()

    return {
        "depth": depth,
        "success_rate_24h": success_rate,
        "failed_24h": failed_24h,
        "avg_generation_seconds": round(float(avg_seconds), 1) if avg_seconds else None,
        "spend_today": round(spend.spent_last_day(db), 2),
        "worker": {"alive": worker_alive, "last_beat": _iso(beat_at), "name": beat_by},
        "jobs": [
            {
                "id": str(j.id), "short_id": str(j.id)[:8], "status": j.status,
                "attempts": j.attempts, "error": j.error,
                "created_at": _iso(j.created_at), "locked_at": _iso(j.locked_at),
                "finished_at": _iso(j.finished_at), "locked_by": j.locked_by,
                "clip_id": str(c.id), "take": c.take, "clip_status": c.status,
                "current_step": c.current_step,
                "cost_usd": float(c.cost_usd) if c.cost_usd is not None else None,
                "user_email": email,
            }
            for j, c, email in rows
        ],
    }


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: uuid.UUID, body: ReasonBody = Body(default=ReasonBody()),
              admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "No such job")
    if j.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried.")
    c = db.get(Clip, j.clip_id)
    if c is not None and c.status == "failed":
        c.status = "queued"
        c.stage_index = 0
        c.error = None
    j.status = "queued"
    j.error = None
    j.run_after = _now()
    _audit(db, admin, "retry_job", f"job {str(j.id)[:8]}", body.reason)
    db.commit()
    return {"ok": True}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, body: ReasonBody = Body(default=ReasonBody()),
               admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "No such job")
    if j.status != "queued":
        raise HTTPException(409, "Only queued jobs can be cancelled "
                                 "(a running render finishes or fails on its own).")
    j.status = "failed"
    j.error = "cancelled by admin"
    j.finished_at = _now()
    c = db.get(Clip, j.clip_id)
    if c is not None and c.status in PROCESSING_STATUSES:
        c.status = "failed"
        c.error = "Cancelled by an operator."
    _audit(db, admin, "cancel_job", f"job {str(j.id)[:8]}", body.reason)
    db.commit()
    return {"ok": True}


@router.get("/settings/spend")
def get_spend_settings(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    return {
        "daily_cap": runtime_settings.daily_cap(db),
        "job_cap": runtime_settings.job_cap(db),
        "paused": runtime_settings.generation_paused(db),
        "spent_24h": round(spend.spent_last_day(db), 2),
        "env_defaults": {
            "daily_cap": float(getattr(settings, "MAX_DAILY_SPEND_USD", 0) or 0),
            "job_cap": float(getattr(settings, "MAX_JOB_COST_USD", 0) or 0),
        },
    }


class SpendSettingsBody(BaseModel):
    daily_cap: float | None = None
    job_cap: float | None = None
    paused: bool | None = None
    reason: str = ""


@router.put("/settings/spend")
def put_spend_settings(body: SpendSettingsBody,
                       admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    if body.daily_cap is not None:
        if body.daily_cap < 0:
            raise HTTPException(422, "daily_cap must be ≥ 0")
        old = runtime_settings.daily_cap(db)
        runtime_settings.set_value(db, runtime_settings.KEY_DAILY_CAP,
                                   str(body.daily_cap), admin.email)
        _audit(db, admin, "set_daily_cap", f"${old:g} → ${body.daily_cap:g}", body.reason)
    if body.job_cap is not None:
        if body.job_cap < 0:
            raise HTTPException(422, "job_cap must be ≥ 0")
        old = runtime_settings.job_cap(db)
        runtime_settings.set_value(db, runtime_settings.KEY_JOB_CAP,
                                   str(body.job_cap), admin.email)
        _audit(db, admin, "set_job_cap", f"${old:g} → ${body.job_cap:g}", body.reason)
    if body.paused is not None:
        runtime_settings.set_value(db, runtime_settings.KEY_PAUSED,
                                   "true" if body.paused else "false", admin.email)
        _audit(db, admin, "pause_generation" if body.paused else "resume_generation",
               "kill switch", body.reason)
    db.commit()
    return get_spend_settings(admin, db)


# -------------------------------------------------------------------- costs


@router.get("/costs")
def costs(days: int = Query(7, ge=1, le=90),
          admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    now = _now()
    since = now - timedelta(days=days)

    total = float(db.scalar(select(func.coalesce(func.sum(Clip.cost_usd), 0))
                            .where(Clip.created_at >= since)) or 0)
    today = float(db.scalar(select(func.coalesce(func.sum(Clip.cost_usd), 0))
                            .where(Clip.created_at >= now - timedelta(hours=24))) or 0)
    costed = db.scalar(select(func.count(Clip.id)).where(
        Clip.created_at >= since, Clip.cost_usd.is_not(None), Clip.cost_usd > 0)) or 0
    failed_cost = float(db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0))
        .where(Clip.created_at >= since, Clip.status == "failed")) or 0)
    active_users = db.scalar(
        select(func.count(distinct(Event.user_id))).where(
            Event.created_at >= since, Event.user_id.is_not(None))) or 0

    by_day_rows = db.execute(
        select(func.date_trunc("day", Clip.created_at).label("day"),
               func.coalesce(func.sum(Clip.cost_usd), 0))
        .where(Clip.created_at >= now - timedelta(days=14))
        .group_by("day").order_by("day")
    ).all()

    # Breakdown + quality reasons come from provenance (python-side; the row
    # count at MVP scale is tiny).
    prov_rows = db.execute(
        select(Clip.cost_usd, Clip.provenance, Clip.status, Clip.error)
        .where(Clip.created_at >= since)
    ).all()
    video_cost = 0.0
    # reason text -> [count, source]; source explains where the signal came
    # from: "review" (automated quality check rejected a scene), "fallback"
    # (pipeline degraded but delivered), "failure" (whole run failed).
    reasons: dict[str, list] = {}

    def add_reason(raw, source: str) -> None:
        key = str(raw)[:60]
        entry = reasons.setdefault(key, [0, source])
        entry[0] += 1

    attempts_total = 0
    scenes_total = 0
    scenes_flagged = 0
    for cost_usd, prov, clip_status, clip_error in prov_rows:
        prov = prov or {}
        for scene in prov.get("scenes") or []:
            video_cost += float(scene.get("cost_usd") or 0)
            attempts_total += int(scene.get("attempts") or 1)
            scenes_total += 1
            hard = scene.get("hard") or []
            if hard:
                scenes_flagged += 1
            for reason in hard:
                add_reason(reason, "review")
        for warning in prov.get("warnings") or []:
            add_reason(warning, "fallback")
        if clip_status == "failed" and clip_error:
            add_reason(clip_error, "failure")
    other_cost = max(total - video_cost, 0.0)

    ready = db.scalar(select(func.count(Clip.id)).where(
        Clip.created_at >= since, Clip.status == "ready")) or 0
    failed = db.scalar(select(func.count(Clip.id)).where(
        Clip.created_at >= since, Clip.status == "failed")) or 0
    retries = db.scalar(select(func.count(Event.id)).where(
        Event.created_at >= since, Event.name == "generation_retried")) or 0

    top_reasons = sorted(reasons.items(), key=lambda kv: kv[1][0], reverse=True)[:8]
    reasons_total = sum(entry[0] for _, entry in top_reasons) or 1

    return {
        "range_days": days,
        "total": round(total, 2), "today": round(today, 2),
        "cost_per_video": round(total / costed, 2) if costed else None,
        "cost_per_active_user": round(total / active_users, 2) if active_users else None,
        "failed_generation_cost": round(failed_cost, 2),
        "failed_cost_pct": round(failed_cost / total * 100, 1) if total else 0.0,
        "provider_balance": provider_balance.get(),
        "by_day": [{"day": d.strftime("%b %d"), "cost": round(float(v), 2)}
                   for d, v in by_day_rows],
        "breakdown": {"video_scenes": round(video_cost, 2), "other": round(other_cost, 2)},
        "quality": {
            "success_rate_pct": round(ready / (ready + failed) * 100, 1)
            if (ready + failed) else None,
            "avg_scene_attempts": round(attempts_total / scenes_total, 2)
            if scenes_total else None,
            "scenes_reviewed": scenes_total,
            "scenes_flagged": scenes_flagged,
            "retries": retries,
            "failure_reasons": [
                {"reason": r, "count": n, "source": source,
                 "pct": round(n / reasons_total * 100)}
                for r, (n, source) in top_reasons
            ],
        },
    }


# ------------------------------------------------------------------ revenue


@router.get("/revenue")
def revenue(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    total_users = db.scalar(select(func.count(User.id))) or 0
    paying = db.scalar(select(func.count(User.id)).where(User.plan == "creator")) or 0
    cancel_pending = db.scalar(select(func.count(User.id)).where(
        User.plan == "creator", User.cancel_at_period_end.is_(True))) or 0
    mrr = round(paying * CREATOR_PRICE_USD, 2)
    cost_30d = float(db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0))
        .where(Clip.created_at >= _now() - timedelta(days=30))) or 0)

    billing_names = ("upgrade_completed", "upgrade_started", "plan_cancelled",
                     "plan_downgraded", "duplicate_subscription_cancelled")
    activity = db.execute(
        select(Event.name, Event.created_at, User.email)
        .outerjoin(User, User.id == Event.user_id)
        .where(Event.name.in_(billing_names))
        .order_by(Event.created_at.desc()).limit(15)
    ).all()
    stripe_evts = db.execute(
        select(StripeEvent).order_by(StripeEvent.event_created_at.desc()).limit(15)
    ).scalars().all()

    return {
        "mrr": mrr, "paying_users": paying, "cancel_pending": cancel_pending,
        "free_users": total_users - paying,
        "conversion_pct": round(paying / total_users * 100, 1) if total_users else 0.0,
        "creator_price": CREATOR_PRICE_USD,
        "gross_profit_30d": round(mrr - cost_30d, 2),
        "ai_cost_30d": round(cost_30d, 2),
        "stripe_dashboard_url": "https://dashboard.stripe.com",
        "activity": [{"name": n, "at": _iso(at), "email": email}
                     for n, at, email in activity],
        "stripe_events": [{"id": e.id, "type": e.type,
                           "at": _iso(e.event_created_at)} for e in stripe_evts],
        "credits_enabled": False,
    }


# --------------------------------------------------------------- publishing


@router.get("/publishing")
def publishing_view(admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    now = _now()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    posts_today = db.scalar(select(func.count(Publish.id)).where(
        Publish.created_at >= day_ago)) or 0
    published_7d = db.scalar(select(func.count(Publish.id)).where(
        Publish.created_at >= week_ago, Publish.status == "published")) or 0
    failed_7d = db.scalar(select(func.count(Publish.id)).where(
        Publish.created_at >= week_ago, Publish.status == "failed")) or 0
    in_flight = db.scalar(select(func.count(Publish.id)).where(
        Publish.status.in_(("queued", "uploading")))) or 0
    connected = db.scalar(select(func.count(SocialAccount.id)).where(
        SocialAccount.status == "connected")) or 0
    expiring = db.scalar(select(func.count(SocialAccount.id)).where(
        SocialAccount.status == "connected",
        SocialAccount.token_expires_at.is_not(None),
        SocialAccount.token_expires_at < now + timedelta(days=7))) or 0
    revoked = db.scalar(select(func.count(SocialAccount.id)).where(
        SocialAccount.status == "revoked")) or 0

    queue = db.execute(
        select(Publish, Clip.take, SocialAccount.handle)
        .join(Clip, Clip.id == Publish.clip_id)
        .outerjoin(SocialAccount, SocialAccount.id == Publish.social_account_id)
        .order_by(Publish.created_at.desc()).limit(12)
    ).all()

    return {
        "posts_today": posts_today,
        "published_7d": published_7d, "failed_7d": failed_7d,
        "success_rate_7d": round(published_7d / (published_7d + failed_7d) * 100, 1)
        if (published_7d + failed_7d) else None,
        "in_flight": in_flight,
        "platforms": [{
            "platform": "instagram", "label": "Instagram Reels", "live": True,
            "connected_accounts": connected, "expiring_tokens": expiring,
            "revoked_accounts": revoked,
        }],
        "coming_soon": ["TikTok", "YouTube Shorts", "X"],
        "queue": [
            {"id": str(p.id), "take": take, "handle": handle, "status": p.status,
             "error": p.error, "external_url": p.external_url,
             "created_at": _iso(p.created_at), "published_at": _iso(p.published_at)}
            for p, take, handle in queue
        ],
    }


@router.post("/publishes/{publish_id}/retry")
def retry_publish(publish_id: uuid.UUID, body: ReasonBody = Body(default=ReasonBody()),
                  admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    p = db.get(Publish, publish_id)
    if p is None:
        raise HTTPException(404, "No such publish")
    if p.status != "failed":
        raise HTTPException(409, "Only failed publishes can be retried.")
    p.status = "queued"
    p.error = None
    _audit(db, admin, "retry_publish", f"publish {str(p.id)[:8]}", body.reason)
    db.commit()
    start_publish(p.id)
    return {"ok": True}


# -------------------------------------------------------------------- audit


@router.get("/audit")
def audit_log(page: int = Query(1, ge=1), action: str = "", admin_email: str = "",
              admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    stmt = select(AdminAction)
    if action:
        stmt = stmt.where(AdminAction.action == action)
    if admin_email:
        stmt = stmt.where(AdminAction.admin_email == admin_email)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(AdminAction.created_at.desc())
        .limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)
    ).scalars().all()
    actions = db.execute(select(distinct(AdminAction.action))).scalars().all()
    admins = db.execute(select(distinct(AdminAction.admin_email))).scalars().all()
    return {
        "total": total, "page": page, "page_size": PAGE_SIZE,
        "actions": sorted(actions), "admins": sorted(admins),
        "entries": [
            {"id": str(a.id), "admin": a.admin_email, "action": a.action,
             "target": a.target, "reason": a.reason, "at": _iso(a.created_at)}
            for a in rows
        ],
    }


# ------------------------------------------------------------------ credits


@router.get("/credits")
def credits_view(admin: User = Depends(get_admin_user)):
    """Placeholder until the credit ledger ships (PRICING.md).

    The frontend renders a "not live yet" state from ``enabled: false``.
    When the ledger lands, this endpoint grows the issued/consumed KPIs and
    ledger listing — nothing else in the console assumes credits exist.
    """
    return {
        "enabled": False,
        "note": "Credit-based pricing is specified in PRICING.md but not yet "
                "integrated. Costs elsewhere in the console are provider USD.",
        "price_list": CREDIT_PRICE_LIST,
    }
