"""The credit system (PRICING.md / UNIT-ECONOMICS-TABLE.md).

One wallet per user; every AI action draws from it. The rules implemented
here, in the doc's words:

- Prices are an exact menu lookup (duration × mode) — internal retries and
  shot counts never change what a user pays.
- Pay only for the finished video: the balance is checked at create/resume,
  but the single charge happens in `charge_on_completion` when the video
  lands. Failures, pauses and abandoned scripts never touch the wallet.
  (`refund_video` remains for clips created under the old reserve-at-start
  model that were still in flight at the changeover.)
- Out of credits → top up, never upgrade. The API returns
  `insufficient_credits` with the exact shortfall; no code path suggests a
  plan change.
- Prices are admin-tunable without a release: a JSON runtime setting
  overrides the defaults below (admin console → Credits).

Money never appears user-side; dollars exist only in the admin console.
"""

from __future__ import annotations

import json
import math
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Clip, CreditEntry, User

log = logging.getLogger("banter.credits")

SETTING_KEY = "credit_prices"

# Launch numbers from UNIT-ECONOMICS-TABLE.md. The per-second rates are the
# rule everything derives from: Standard (720p) 4 cr/s, HD (1080p) 7 cr/s.
DEFAULTS: dict = {
    "per_second": {"720p": 4, "1080p": 7},
    "enhance_take": 1,
    "signup_grant": 60,       # one 15s Standard video — the full wow, once
    "monthly_grant": 150,     # Creator's monthly drop
    "packs": [
        {"key": "starter", "credits": 100, "usd": 12},
        {"key": "creator", "credits": 300, "usd": 29, "popular": True},
        {"key": "pro", "credits": 750, "usd": 59},
        {"key": "studio", "credits": 2000, "usd": 129},
    ],
}


def prices(db: Session) -> dict:
    """The live price config: defaults overlaid with the admin override."""
    merged = json.loads(json.dumps(DEFAULTS))
    try:
        from . import runtime_settings

        raw = runtime_settings.get_raw(db, SETTING_KEY)
        if raw:
            saved = json.loads(raw)
            if isinstance(saved, dict):
                for key, value in saved.items():
                    if key in merged and type(value) is type(merged[key]):
                        merged[key] = value
    except Exception:  # noqa: BLE001 — bad override must not break pricing
        log.exception("credit price override unreadable; using defaults")
    return merged


def video_price(db: Session, duration: int, resolution: str) -> int:
    """Exact menu price for a video — quoted before, charged after."""
    cfg = prices(db)
    per_s = cfg["per_second"].get(str(resolution or "720p"), cfg["per_second"]["720p"])
    return int(per_s) * max(1, int(duration or 15))


def scene_price(db: Session, seconds: float, resolution: str) -> int:
    """Exact price to re-render ONE scene of a finished video: its length at
    the same per-second rate as the video, rounded up to a whole credit."""
    cfg = prices(db)
    per_s = cfg["per_second"].get(str(resolution or "720p"), cfg["per_second"]["720p"])
    return max(1, math.ceil(float(seconds or 0.0) * int(per_s)))


def pack(db: Session, key: str) -> dict | None:
    return next((p for p in prices(db)["packs"] if p.get("key") == key), None)


def apply(db: Session, user: User, delta: int, kind: str,
          clip: Clip | None = None, note: str = "",
          allow_negative: bool = False) -> int:
    """Move credits atomically and write the ledger row. Returns the new
    balance. A debit that would go below zero raises ValueError — callers
    check first and answer with `insufficient_credits`; this is the backstop
    against concurrent spends.

    `allow_negative` exists for exactly one caller: charging a video that has
    already finished rendering. The user was balance-checked at create and at
    resume, so a negative here means parallel spends raced — the debt is
    real, the video is real, and refusing the charge would make the video
    free instead."""
    delta = int(delta)
    guard = [User.id == user.id]
    if not allow_negative:
        guard.append(User.credits + delta >= 0)
    row = db.execute(
        update(User)
        .where(*guard)
        .values(credits=User.credits + delta)
        .returning(User.credits)
    ).first()
    if row is None:
        db.rollback()
        raise ValueError("insufficient credits")
    balance = int(row[0])
    db.add(CreditEntry(user_id=user.id, delta=delta, balance_after=balance,
                       kind=kind, clip_id=clip.id if clip is not None else None,
                       note=note or None))
    db.commit()
    db.refresh(user)
    return balance


def charge_on_completion(db: Session, user: User, clip: Clip) -> int:
    """The charge, taken only when the finished video exists.

    Nothing is reserved up front any more: the balance is checked at create
    and at resume, and the wallet moves exactly once, here. Idempotent via
    credits_charged (a legacy clip that reserved at create keeps its charge
    and is skipped), and simulated clips are always free."""
    if clip.is_simulated or int(clip.credits_charged or 0) > 0:
        return int(clip.credits_charged or 0)
    amount = int(clip.credits_quoted or 0) or video_price(
        db, clip.duration_target, clip.resolution)
    clip.credits_charged = amount
    apply(db, user, -amount, "video_charge", clip=clip,
          note=f"{clip.duration_target}s {clip.resolution}", allow_negative=True)
    return amount


def charge_edit(db: Session, user: User, clip: Clip, amount: int, note: str = "") -> int:
    """The single charge for a finished scene edit — same rules as the video
    charge: only once the new cut exists, and never refused (the balance was
    checked when the edit was requested)."""
    amount = int(amount or 0)
    if clip.is_simulated or amount <= 0:
        return 0
    clip.credits_edits = int(clip.credits_edits or 0) + amount
    apply(db, user, -amount, "edit_charge", clip=clip,
          note=note or "scene edit", allow_negative=True)
    return amount


def refund_video(db: Session, clip: Clip) -> bool:
    """Release a clip's reservation — failures and abandonment are free.

    Idempotent: the atomic credits_charged→0 update means exactly one caller
    wins, however many failure paths fire for the same clip."""
    amount = int(clip.credits_charged or 0)
    if amount <= 0:
        return False
    row = db.execute(
        update(Clip)
        .where(Clip.id == clip.id, Clip.credits_charged == amount)
        .values(credits_charged=0)
        .returning(Clip.user_id)
    ).first()
    if row is None:  # another path already released it
        db.rollback()
        return False
    clip.credits_charged = 0
    user = db.get(User, row[0])
    if user is None:
        db.commit()
        return False
    apply(db, user, amount, "video_refund", clip=clip, note="generation failed or abandoned")
    return True


def grant_signup(db: Session, user: User) -> None:
    amount = int(prices(db)["signup_grant"])
    if amount > 0:
        apply(db, user, amount, "grant_signup", note="welcome credits")


def maybe_grant_monthly(db: Session, user: User) -> bool:
    """Creator's monthly drop, granted lazily (checked on /me/usage).

    Webhook-independent on purpose: renewals grant on the user's next visit
    even if Stripe's invoice events were never subscribed. The 28-day guard
    is the idempotency: one grant per billing month, however often called."""
    if user.plan != "creator":
        return False
    last = db.scalar(
        select(CreditEntry.created_at)
        .where(CreditEntry.user_id == user.id, CreditEntry.kind == "grant_monthly")
        .order_by(CreditEntry.created_at.desc())
        .limit(1)
    )
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last < timedelta(days=28):
            return False
    amount = int(prices(db)["monthly_grant"])
    if amount <= 0:
        return False
    apply(db, user, amount, "grant_monthly", note="Creator monthly credits")
    log.info("monthly grant: %s +%d", user.email, amount)
    return True
