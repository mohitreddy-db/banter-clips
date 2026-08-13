import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event, usage_for
from ..models import Clip, Publish, SocialAccount, User
from ..schemas import (
    CaptionSuggestions,
    ClipCreate, ClipOut, EnhanceOut, EnhanceRequest, PublishCreate, PublishOut,
    TakeEnhanceRequest, TakeEnhanceResponse, TakeVariation,
)
from ..services import markers, storage
from ..services.generation import start_generation
from ..services.publishing import start_publish

log = logging.getLogger("banter.clips")

router = APIRouter(prefix="/clips", tags=["clips"])


def _own_clip(clip_id: uuid.UUID, user: User, db: Session) -> Clip:
    clip = db.scalar(
        select(Clip).options(selectinload(Clip.publishes)).where(Clip.id == clip_id)
    )
    # BR-02/BR-12: a user can only ever see their own clips.
    if clip is None or clip.user_id != user.id:
        raise HTTPException(404, "Clip not found")
    return clip


def _serialize(clip: Clip) -> ClipOut:
    out = ClipOut.model_validate(clip)
    for pub_out, pub in zip(out.publishes, clip.publishes):
        pub_out.platform = pub.account.platform if pub.account else None
        pub_out.handle = pub.account.handle if pub.account else None
    if clip.poster_key:
        try:
            out.poster_url = storage.get().url(clip.poster_key)
        except Exception:  # noqa: BLE001 — a thumbnail is never worth a 500
            log.warning("could not build a poster URL for clip %s", clip.id)
    return out


@router.get("", response_model=list[ClipOut])
def list_clips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clips = db.scalars(
        select(Clip)
        .options(selectinload(Clip.publishes))
        .where(Clip.user_id == user.id)
        .order_by(Clip.created_at.desc())
    ).all()
    return [_serialize(c) for c in clips]


@router.post("/enhance", response_model=EnhanceOut)
def enhance_take(
    body: EnhanceRequest,
    user: User = Depends(get_current_user),
):
    """Sharpen a take and report what is still worth asking the user.

    Read-only and cheap (one small text call, no image or video work), so the
    client may call it on every edit of an answer. Answers from a previous
    round come back in `answers`; the questions they resolved disappear.

    Never fails: with no key or a broken model the brief falls back to the
    take as written, and generation would still run.
    """
    from ..video import enhancer, providers

    # enhance() already folds in `answers` and drops the questions they
    # resolved. Calling apply_answers() on top would seed every remaining
    # question with its own default and silently answer all of them.
    brief = enhancer.enhance(
        body.take, body.sport, body.tone, body.duration,
        answers=body.answers, client=providers.text_client(),
    )
    return EnhanceOut(**brief.to_dict())


@router.post("/enhance-take", response_model=TakeEnhanceResponse)
def enhance_take_variations(
    body: TakeEnhanceRequest,
    user: User = Depends(get_current_user),
):
    """Two sharper versions of a take, for the input page.

    Called on demand and repeatedly — every press returns two NEW variations,
    and the original is echoed back so the client can always offer it as the
    third choice. Nothing is generated and no allowance is touched.

    An empty `variations` list is a valid answer: it means keep what you
    wrote, which is never the wrong outcome.
    """
    from ..video import providers, takes

    options = takes.variations(
        body.take, body.sport or "NBA", body.tone or "Funny",
        client=providers.text_client(), round_index=body.round,
    )
    return TakeEnhanceResponse(
        original=body.take.strip(),
        variations=[TakeVariation(**o) for o in options],
    )


@router.post("", response_model=ClipOut, status_code=201)
def create_clip(body: ClipCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # A demo run costs nothing and produces nothing publishable, so it must
    # not be charged against the monthly allowance or gated by it.
    simulated = markers.is_simulated(body.take)

    usage = usage_for(db, user)
    if not simulated and usage["left"] <= 0:
        # BR-09: at the limit → upgrade prompt, never a silent failure.
        raise HTTPException(
            402,
            detail={
                "code": "limit_reached",
                "message": f"You've used all {usage['limit']} videos on the "
                f"{user.plan} plan this month.",
            },
        )

    # Longer videos are a Creator feature (Free tops out at 15s).
    if body.duration > 15 and user.plan != "creator":
        raise HTTPException(
            403,
            detail={
                "code": "upgrade_required",
                "message": "Videos longer than 15 seconds are a Creator feature.",
            },
        )

    clip = Clip(
        user_id=user.id,
        # Markers are stripped so they can never surface in the video, the
        # captions, or a published Instagram caption.
        take=markers.strip(body.take),
        is_simulated=simulated,
        sport=body.sport,
        tone=body.tone,
        duration_target=body.duration,
        # Watermark policy frozen per-clip from the plan at creation time.
        watermarked=user.plan != "creator",
    )
    db.add(clip)
    db.commit()
    record_event(db, "generation_started", user, sport=body.sport, tone=body.tone, duration=body.duration)
    start_generation(clip.id)
    return _serialize(clip)


@router.get("/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize(_own_clip(clip_id, user, db))


@router.post("/{clip_id}/retry", response_model=ClipOut)
def retry_clip(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clip = _own_clip(clip_id, user, db)
    if clip.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried.")
    # BR-09: retries are free — the allowance is only charged on success.
    clip.status = "queued"
    clip.stage_index = 0
    clip.error = None
    # Strip the demo failure marker so the retry succeeds.
    clip.take = clip.take.replace("[fail]", "").replace("[FAIL]", "").strip()
    if len(clip.take) < 10:
        clip.take = clip.take + " (retried take)"
    db.commit()
    record_event(db, "generation_retried", user)
    start_generation(clip.id)
    return _serialize(clip)


@router.delete("/{clip_id}", status_code=204)
def delete_clip(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clip = _own_clip(clip_id, user, db)
    # Delete the bytes too. Dropping only the row leaves the video publicly
    # fetchable at its URL forever — a deletion that does not delete.
    try:
        storage.get().delete_prefix(storage.clip_prefix(clip.user_id, clip.id))
    except Exception:  # noqa: BLE001 — never block a deletion on storage
        log.exception("could not remove artifacts for clip %s", clip.id)
    db.delete(clip)
    db.commit()


@router.get("/{clip_id}/download")
def download_clip(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clip = _own_clip(clip_id, user, db)
    if clip.status != "ready":
        raise HTTPException(409, "This clip isn't ready yet.")
    # Client non-negotiable: Free is publish-only. Download = Creator.
    if user.plan != "creator":
        raise HTTPException(
            403,
            detail={
                "code": "upgrade_required",
                "message": "Downloading in HD without the watermark is a Creator feature.",
            },
        )
    record_event(db, "video_downloaded", user, clip_id=str(clip.id))
    filename = f"banterclips-{clip.sport.lower()}-{str(clip.id)[:8]}.mp4"

    # Serve THIS clip. An earlier version returned the demo file unconditionally,
    # which meant a paying customer downloaded somebody else's video with their
    # own filename on it — silent, and wrong in the worst direction.
    store = storage.get()
    if clip.video_key:
        path = store.local_path(clip.video_key)
        if path:
            return FileResponse(path, media_type="video/mp4", filename=filename)
        payload = store.open(clip.video_key)
        if payload:
            return Response(
                payload,
                media_type="video/mp4",
                headers={"content-disposition": f'attachment; filename="{filename}"'},
            )

    # Pre-storage clips (and simulated ones) kept only a URL. Fall back to the
    # legacy path rather than failing a download the user has paid for.
    legacy = settings.MEDIA_DIR / f"{clip.id}.mp4"
    if legacy.exists():
        return FileResponse(legacy, media_type="video/mp4", filename=filename)
    if clip.is_simulated:
        demo = settings.MEDIA_DIR / "demo.mp4"
        if demo.exists():
            return FileResponse(demo, media_type="video/mp4", filename=filename)
    raise HTTPException(410, "This clip's file is no longer available.")


@router.get("/{clip_id}/captions", response_model=CaptionSuggestions)
def caption_suggestions(
    clip_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Three caption options for this clip, to pick between when publishing.

    Cheap and read-only. Always returns three, falling back to deterministic
    options if the model is unavailable — an empty picker is worse than a
    plain one.
    """
    clip = _own_clip(clip_id, user, db)
    from ..video import captions as caption_writer, providers

    options = caption_writer.suggest(
        clip.take, clip.sport, clip.tone, client=providers.text_client()
    )
    return CaptionSuggestions(captions=options)


@router.post("/{clip_id}/publish", response_model=PublishOut, status_code=201)
def publish_clip(
    clip_id: uuid.UUID,
    body: PublishCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clip = _own_clip(clip_id, user, db)
    if clip.status != "ready":
        raise HTTPException(409, "Only completed clips can be published.")
    if clip.is_simulated:
        # Demo clips publish like any other. They hold a real, watchable video
        # stored at their own key — it just was not generated from this take,
        # so the caption and the footage can disagree. Allowed deliberately:
        # publishing is the last step of the flow and demoing it end to end is
        # worth more than protecting against a mismatch the user chose by
        # typing [mock]. Recorded so it is visible in analytics.
        log.info("publishing simulated clip %s for user %s", clip.id, user.id)

    account = db.get(SocialAccount, body.social_account_id)
    if account is None or account.user_id != user.id or account.status != "connected":
        raise HTTPException(400, "Connect a social account before publishing.")

    # BR-13: publishing is always an explicit per-clip action.
    pub = Publish(clip_id=clip.id, social_account_id=account.id, caption=body.caption)
    db.add(pub)
    db.commit()
    record_event(db, "publish_started", user, clip_id=str(clip.id),
                 platform=account.platform, simulated=clip.is_simulated)
    start_publish(pub.id)

    out = PublishOut.model_validate(pub)
    out.platform = account.platform
    out.handle = account.handle
    return out


@router.get("/{clip_id}/publishes/{publish_id}", response_model=PublishOut)
def get_publish(
    clip_id: uuid.UUID,
    publish_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _own_clip(clip_id, user, db)
    pub = db.get(Publish, publish_id)
    if pub is None or pub.clip_id != clip_id:
        raise HTTPException(404, "Publish attempt not found")
    out = PublishOut.model_validate(pub)
    out.platform = pub.account.platform if pub.account else None
    out.handle = pub.account.handle if pub.account else None
    return out
