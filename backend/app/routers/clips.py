import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
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

REFERENCE_LIMIT = 15 * 1024 * 1024
REFERENCE_TYPES = {"image/jpeg": ".jpg", "video/mp4": ".mp4"}


def reference_matches(payload: bytes, suffix: str) -> bool:
    return payload.startswith(b"\xff\xd8\xff") if suffix == ".jpg" else payload[4:8] == b"ftyp"


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
    db: Session = Depends(get_db),
):
    """Two sharper versions of a take, for the input page.

    Called on demand and repeatedly — every press returns two NEW variations,
    and the original is echoed back so the client can always offer it as the
    third choice. Costs 1 credit per press (PRICING §4) — charged up front,
    which is also the farming guard.

    An empty `variations` list is a valid answer: it means keep what you
    wrote, which is never the wrong outcome.
    """
    from ..services import credits
    from ..video import providers, sports as sports_mod, takes

    fee = int(credits.prices(db)["enhance_take"])
    if fee > 0:
        try:
            credits.apply(db, user, -fee, "enhance_charge", note="enhance take")
        except ValueError:
            raise HTTPException(402, detail={
                "code": "insufficient_credits",
                "message": f"Enhancing costs {fee} credit — you have {user.credits}.",
                "needed": fee, "balance": user.credits,
            })
    options = takes.variations(
        body.take, sports_mod.resolve(body.sport, body.take), body.tone or "Funny",
        client=providers.text_client(), round_index=body.round,
    )
    return TakeEnhanceResponse(
        original=body.take.strip(),
        variations=[TakeVariation(**o) for o in options],
    )


@router.get("/trending")
def trending(sport: str = "NBA", user: User = Depends(get_current_user)):
    """The trending feed for the create page.

    Shared 20-minute cache per sport (see app/video/trending.py), so this is
    cheap to call on every page open. Free — trending exists to drive
    generation (PRICING.md §11). Returns an empty feed when web research is
    off; the client hides the section.

    Declared before GET /{clip_id}: "trending" must match this route, not
    the uuid path.
    """
    from ..video import trending as trending_feed

    return trending_feed.get_feed(sport)


@router.post("", response_model=ClipOut, status_code=201)
def create_clip(body: ClipCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..services import credits

    # A demo run costs nothing and produces nothing publishable, so it must
    # not be charged credits or gated by the balance.
    simulated = markers.is_simulated(body.take)

    # The exact menu quote. The balance is only CHECKED here — the single
    # charge happens when the finished video lands (charge_on_completion),
    # so a failed or paused generation never touches the wallet.
    price = 0 if simulated else credits.video_price(db, body.duration, body.resolution)
    if user.credits < price:
        # PRICING rule 2: an empty balance means top up — never an upgrade
        # prompt, and never a plan mention.
        raise HTTPException(
            402,
            detail={
                "code": "insufficient_credits",
                "message": f"This video needs {price} credits — you have {user.credits}.",
                "needed": price,
                "balance": user.credits,
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

    # Full HD is a Creator feature (Free renders at 720p).
    if body.resolution == "1080p" and user.plan != "creator":
        raise HTTPException(
            403,
            detail={
                "code": "upgrade_required",
                "message": "1080p video is a Creator feature — Free renders at 720p.",
            },
        )

    # Sport is optional (a take usually names its own league or player), and
    # multi-select: the first pick is the world the video is built in, the
    # rest are context. Nothing here can fail — resolve always answers.
    from ..video import sports as sports_mod

    picked = [s for s in ([body.sport] if body.sport else []) + list(body.sports) if s]
    primary = sports_mod.resolve(
        picked[0] if picked else None,
        body.take,
        (user.preferences.sports if user.preferences else None) or [],
    )
    subjects = [s.strip()[:60] for s in body.subjects if s and s.strip()][:8]

    clip = Clip(
        user_id=user.id,
        # Markers are stripped so they can never surface in the video, the
        # captions, or a published Instagram caption.
        take=markers.strip(body.take),
        is_simulated=simulated,
        sport=primary,
        sports=list(dict.fromkeys(picked)),
        subjects=subjects,
        direction=body.direction.strip(),
        credits_quoted=price,
        tone=body.tone,
        duration_target=body.duration,
        resolution=body.resolution,
        # Watermark policy frozen per-clip from the plan at creation time.
        watermarked=user.plan != "creator",
    )
    db.add(clip)
    db.flush()
    if body.reference_key:
        expected = f"users/{user.id}/uploads/"
        if not body.reference_key.startswith(expected):
            raise HTTPException(400, "Invalid reference upload")
        store = storage.get()
        payload = store.open(body.reference_key)
        if payload is None:
            raise HTTPException(400, "Reference upload expired — choose it again")
        suffix = ".mp4" if body.reference_key.endswith(".mp4") else ".jpg"
        key = f"{storage.clip_prefix(user.id, clip.id)}/reference{suffix}"
        store.put(key, payload, "video/mp4" if suffix == ".mp4" else "image/jpeg")
        store.delete(body.reference_key)
        clip.reference_key = key
    db.commit()
    record_event(db, "generation_started", user, sport=primary, tone=body.tone,
                 duration=body.duration, inferred_sport=not picked)
    start_generation(clip.id)
    return _serialize(clip)


@router.post("/reference", status_code=201)
async def upload_reference(
    request: Request,
    user: User = Depends(get_current_user),
):
    """One optional JPEG or MP4 reference for the guided prompt builder.

    Raw-body upload avoids a multipart dependency. The key is temporary and
    is moved under the clip when POST /clips succeeds.
    """
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    suffix = REFERENCE_TYPES.get(content_type)
    if not suffix:
        raise HTTPException(415, "Reference must be a JPEG image or MP4 video")
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > REFERENCE_LIMIT:
            raise HTTPException(413, "Reference must be between 1 byte and 15 MB")
    payload = bytes(payload)
    if not payload:
        raise HTTPException(413, "Reference must be between 1 byte and 15 MB")
    if not reference_matches(payload, suffix):
        raise HTTPException(415, "Reference file contents do not match its type")
    key = f"users/{user.id}/uploads/{uuid.uuid4()}{suffix}"
    storage.get().put(key, payload, content_type)
    return {"key": key}


@router.get("/{clip_id}", response_model=ClipOut)
def get_clip(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize(_own_clip(clip_id, user, db))


class SceneEdit(BaseModel):
    index: int = Field(ge=0, le=20)
    line: str | None = Field(default=None, max_length=220)
    action: str | None = Field(default=None, max_length=400)


class ScriptEdit(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    scenes: list[SceneEdit] = Field(default_factory=list, max_length=20)


@router.patch("/{clip_id}/script", response_model=ClipOut)
def edit_script(
    clip_id: uuid.UUID,
    body: ScriptEdit,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The user's own words win: edit dialogue lines and shot actions before
    approving. Lines are trimmed to what fits the shot's seconds — an edit
    must not silently break the video's timing."""
    from ..video.types import Scene

    clip = _own_clip(clip_id, user, db)
    if clip.status != "script_ready" or not clip.script:
        raise HTTPException(409, "This clip has no script awaiting approval.")
    script = dict(clip.script)
    scenes = [dict(s) for s in script.get("scenes", [])]
    for edit in body.scenes:
        if edit.index >= len(scenes):
            continue
        scene = scenes[edit.index]
        if edit.action is not None and edit.action.strip():
            scene["action"] = edit.action.strip()
        if edit.line is not None:
            fitted = Scene(seconds=float(scene.get("seconds") or 4.0),
                           line=edit.line.strip())
            scene["line"] = fitted.trimmed_line() if fitted.line else ""
    script["scenes"] = scenes
    if body.title is not None and body.title.strip():
        script["title"] = body.title.strip()
    script["edited"] = True
    clip.script = script
    db.commit()
    record_event(db, "script_edited", user, clip_id=str(clip.id))
    return _serialize(clip)


class ScriptRegenerate(BaseModel):
    # Optional note telling the writer what was wrong ("less cringe",
    # "make it about the derby") — folded into the rewrite prompt.
    feedback: str = Field(default="", max_length=400)


@router.post("/{clip_id}/script/approve", response_model=ClipOut)
def approve_script(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The user has read the script — spend real money and render it."""
    clip = _own_clip(clip_id, user, db)
    if clip.status != "script_ready" or not clip.script:
        raise HTTPException(409, "This clip has no script awaiting approval.")
    clip.script_approved = True
    clip.status = "queued"
    clip.stage_index = 0
    db.commit()
    record_event(db, "script_approved", user, clip_id=str(clip.id))
    start_generation(clip.id)
    return _serialize(clip)


@router.post("/{clip_id}/script/regenerate", response_model=ClipOut)
def regenerate_script(
    clip_id: uuid.UUID,
    body: ScriptRegenerate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject the current script and write a different one. Free — only the
    render costs real money, and it hasn't started."""
    clip = _own_clip(clip_id, user, db)
    if clip.status != "script_ready" or not clip.script:
        raise HTTPException(409, "This clip has no script awaiting approval.")
    history = list(clip.script_history or [])
    history.append({"script": clip.script, "feedback": body.feedback.strip()})
    clip.script_history = history[-10:]   # rejected drafts, capped
    clip.script = None
    clip.script_approved = False
    clip.status = "queued"
    clip.stage_index = 0
    db.commit()
    record_event(db, "script_regenerated", user, clip_id=str(clip.id),
                 with_feedback=bool(body.feedback.strip()))
    start_generation(clip.id)
    return _serialize(clip)


@router.post("/{clip_id}/retry", response_model=ClipOut)
def retry_clip(clip_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..services import credits

    clip = _own_clip(clip_id, user, db)
    if clip.status not in ("failed", "paused"):
        raise HTTPException(409, "Only failed or paused jobs can be retried.")
    # Nothing is charged here: a resumed job reuses its checkpointed scenes
    # and the single charge happens when the video completes. The balance
    # check just keeps that completion charge from landing on an empty
    # wallet the user already spent elsewhere.
    if not clip.is_simulated and clip.credits_charged <= 0:
        price = clip.credits_quoted or credits.video_price(
            db, clip.duration_target, clip.resolution)
        if user.credits < price:
            raise HTTPException(402, detail={
                "code": "insufficient_credits",
                "message": f"Resuming needs {price} credits available — you have {user.credits}.",
                "needed": price, "balance": user.credits,
            })
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
    from ..services import credits

    clip = _own_clip(clip_id, user, db)
    # Abandoning an unfinished clip (script stage, queue, mid-render) releases
    # its reservation — only a completed video keeps its charge (rule 3).
    if clip.status != "ready":
        credits.refund_video(db, clip)
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
    avoid: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Three caption options for this clip, to pick between when publishing.

    Cheap and read-only. Always returns three, falling back to deterministic
    options if the model is unavailable — an empty picker is worse than a
    plain one. `avoid` carries the captions already shown (newline-separated)
    so a "regenerate" click produces genuinely new ones, not a reshuffle.
    """
    clip = _own_clip(clip_id, user, db)
    from ..video import captions as caption_writer, providers

    options = caption_writer.suggest(
        clip.take, clip.sport, clip.tone,
        client=providers.text_client(),
        avoid=[a.strip() for a in avoid.split("\n") if a.strip()][:9],
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
