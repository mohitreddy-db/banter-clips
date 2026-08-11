import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event, usage_for
from ..models import Clip, Publish, SocialAccount, User
from ..schemas import ClipCreate, ClipOut, PublishCreate, PublishOut
from ..services.generation import start_generation
from ..services.publishing import start_publish

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


@router.post("", response_model=ClipOut, status_code=201)
def create_clip(body: ClipCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    usage = usage_for(db, user)
    if usage["left"] <= 0:
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
        take=body.take.strip(),
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
    return FileResponse(
        settings.MEDIA_DIR / "demo.mp4",
        media_type="video/mp4",
        filename=f"banterclips-{clip.sport.lower()}-{str(clip.id)[:8]}.mp4",
    )


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

    account = db.get(SocialAccount, body.social_account_id)
    if account is None or account.user_id != user.id or account.status != "connected":
        raise HTTPException(400, "Connect a social account before publishing.")

    # BR-13: publishing is always an explicit per-clip action.
    pub = Publish(clip_id=clip.id, social_account_id=account.id, caption=body.caption)
    db.add(pub)
    db.commit()
    record_event(db, "publish_started", user, clip_id=str(clip.id), platform=account.platform)
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
