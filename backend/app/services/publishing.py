"""Publish worker (BR-13).

Two paths, chosen per connected account:
- Real: the account came from a platform OAuth flow → publish for real.
  Instagram: create a Reel container from a public video URL (Meta pulls),
  poll processing, publish, fetch the permalink. TikTok: Direct Post via
  FILE_UPLOAD (we push the bytes, optionally through the US proxy), then
  poll until TikTok finishes processing.
- Mock: the account was created by the dev mock connector → simulate the
  same honest status machine without touching the platform.
"""

import threading
import time
import uuid
from datetime import datetime, timezone

import httpx

from ..config import settings
from ..db import SessionLocal
from ..models import Publish
from . import tiktok, youtube

FAIL_MARKER = "[fail]"
MOCK_TOKEN = "mock-oauth-token"
UPLOAD_SECONDS = 2.2
IG_GRAPH = "https://graph.instagram.com/v23.0"


def _public_video_url(clip) -> str:
    """The URL Meta will fetch the video from. It must be publicly reachable —
    Instagram downloads the file itself and cannot present credentials.

    This used to keep only the last path segment of `clip.video_url` and
    rebuild `{API_BASE_URL}/media/{filename}`, which worked only while every
    clip was the demo file in the local media directory. Once clips moved to
    storage the real path became `users/{uid}/clips/{cid}/final.mp4`, so the
    rebuilt URL resolved to `/media/final.mp4` — a 404. Instagram fetched
    nothing and reported it as "could not process the video", which sent us
    looking at the encoding rather than the URL.

    Use the URL the pipeline recorded. It already points at wherever the clip
    actually lives, local or remote.
    """
    if clip.video_key:
        try:
            from .storage import get as get_storage

            return get_storage().url(clip.video_key)
        except Exception:  # noqa: BLE001 — fall through to the stored URL
            pass
    if clip.video_url:
        return clip.video_url
    return f"{settings.API_BASE_URL}/media/demo.mp4"


def _fail(db, pub, message: str) -> None:
    pub.status = "failed"
    pub.error = message
    db.commit()


def _publish_tiktok(db, pub) -> None:
    account = pub.account
    token = account.access_token

    # 1. TikTok requires asking what the creator may post right now.
    info = tiktok.creator_info(token)
    if (info.get("error") or {}).get("code") not in (None, "ok"):
        msg = (info.get("error") or {}).get("message") or "TikTok rejected the publish request."
        return _fail(db, pub, msg)
    options = (info.get("data") or {}).get("privacy_level_options") or []
    privacy = tiktok.pick_privacy(options)

    # 2. Fetch the finished clip's bytes — we push them, TikTok never needs
    # to reach our storage, so this works from local dev too.
    try:
        response = httpx.get(_public_video_url(pub.clip), timeout=120)
        response.raise_for_status()
        video = response.content
    except httpx.HTTPError:
        return _fail(db, pub, "Could not read the finished video from storage. Retrying is free.")

    # 3. Init the Direct Post, upload, then poll processing.
    init = tiktok.post_init(token, caption=pub.caption or "", privacy=privacy, video_size=len(video))
    if (init.get("error") or {}).get("code") not in (None, "ok") or "data" not in init:
        code = (init.get("error") or {}).get("code") or ""
        if "unaudited" in code:
            # TikTok's rule while an app is unaudited/sandbox: the target
            # ACCOUNT must be private, not just the post's privacy level.
            return _fail(db, pub, "While our TikTok app is in review, TikTok only lets us post to private accounts. Switch your TikTok account to Private (Settings → Privacy → Private account) and retry — it's free.")
        msg = (init.get("error") or {}).get("message") or "TikTok rejected the upload request."
        return _fail(db, pub, msg)
    publish_id = init["data"]["publish_id"]

    try:
        tiktok.upload_video(init["data"]["upload_url"], video)
    except httpx.HTTPError:
        return _fail(db, pub, "The upload to TikTok failed partway. Retrying is free.")

    for _ in range(60):
        time.sleep(3)
        body = tiktok.post_status(token, publish_id)
        status = (body.get("data") or {}).get("status")
        if status == "PUBLISH_COMPLETE":
            post_ids = (body.get("data") or {}).get("publicaly_available_post_id") or []
            pub.status = "published"
            pub.error = None
            pub.published_at = datetime.now(timezone.utc)
            # Public posts get a canonical link (TikTok redirects on the video
            # id, whatever the @segment). Private/sandbox posts have no public
            # URL — the video sits on the creator's own profile.
            pub.external_url = (
                f"https://www.tiktok.com/@_/video/{post_ids[0]}" if post_ids else None
            )
            db.commit()
            return
        if status == "FAILED":
            reason = (body.get("data") or {}).get("fail_reason") or "TikTok could not process the video."
            return _fail(db, pub, f"{reason} Retrying is free.")
    return _fail(db, pub, "TikTok is taking too long to process the video. Retry in a minute.")


def _publish_youtube(db, pub) -> None:
    try:
        response = httpx.get(_public_video_url(pub.clip), timeout=120)
        response.raise_for_status()
        video = response.content
    except httpx.HTTPError:
        return _fail(db, pub, "Could not read the finished video from storage. Retrying is free.")
    title, description = youtube.metadata(pub.caption or "", pub.clip.take)
    try:
        video_id = youtube.upload_short(
            pub.account.access_token,
            video,
            title=title,
            description=description,
        )
    except httpx.HTTPError:
        return _fail(db, pub, "YouTube rejected or interrupted the upload. Check the channel connection and retry — it's free.")
    pub.status = "published"
    pub.error = None
    pub.published_at = datetime.now(timezone.utc)
    pub.external_url = f"https://www.youtube.com/shorts/{video_id}"
    db.commit()


def _real_publish(db, pub) -> None:
    account = pub.account
    clip = pub.clip
    token = account.access_token

    # 1. Create the Reel media container.
    r = httpx.post(
        f"{IG_GRAPH}/{account.platform_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": _public_video_url(clip),
            "caption": pub.caption or "",
            "access_token": token,
        },
        timeout=30,
    )
    body = r.json()
    if "id" not in body:
        msg = (body.get("error") or {}).get("message", "Instagram rejected the upload request.")
        return _fail(db, pub, msg)
    container = body["id"]

    # 2. Wait for Instagram to fetch + process the video.
    for _ in range(60):
        time.sleep(3)
        status = httpx.get(
            f"{IG_GRAPH}/{container}",
            params={"fields": "status_code", "access_token": token},
            timeout=15,
        ).json().get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            return _fail(db, pub, "Instagram could not process the video. Retrying is free.")
    else:
        return _fail(db, pub, "Instagram is taking too long to process the video. Retry in a minute.")

    # 3. Publish the container.
    r = httpx.post(
        f"{IG_GRAPH}/{account.platform_user_id}/media_publish",
        data={"creation_id": container, "access_token": token},
        timeout=30,
    )
    body = r.json()
    if "id" not in body:
        msg = (body.get("error") or {}).get("message", "Instagram refused to publish the Reel.")
        return _fail(db, pub, msg)
    media_id = body["id"]

    # 4. Link to the live post.
    permalink = (
        httpx.get(
            f"{IG_GRAPH}/{media_id}",
            params={"fields": "permalink", "access_token": token},
            timeout=15,
        )
        .json()
        .get("permalink")
    )

    pub.status = "published"
    pub.error = None
    pub.published_at = datetime.now(timezone.utc)
    pub.external_url = permalink or f"https://www.instagram.com/{account.handle.lstrip('@')}/"
    db.commit()


def _mock_publish(db, pub) -> None:
    pub.status = "uploading"
    db.commit()
    time.sleep(UPLOAD_SECONDS)

    # Typing "[fail]" in the caption demos the failed-publish + retry path.
    if FAIL_MARKER in (pub.caption or "").lower():
        return _fail(
            db,
            pub,
            "The platform rejected the upload (simulated). Retrying is free "
            "and never regenerates the video.",
        )

    pub.status = "published"
    pub.error = None
    pub.published_at = datetime.now(timezone.utc)
    pub.external_url = (
        f"https://www.tiktok.com/@banterclips/video/72{str(pub.id.int)[:14]}"
        if pub.account and pub.account.platform == "tiktok"
        else f"https://www.youtube.com/shorts/BC{str(pub.id)[:8]}"
        if pub.account and pub.account.platform == "youtube"
        else f"https://www.instagram.com/reel/BC{str(pub.id)[:8]}/"
    )
    db.commit()


def _run_publish(publish_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        pub = db.get(Publish, publish_id)
        if pub is None:
            return
        account = pub.account
        platform = account.platform if account else "instagram"
        real = bool(account and account.access_token and account.access_token != MOCK_TOKEN and account.platform_user_id)
        # Meta downloads the video from our public URL — with a localhost
        # API_BASE_URL that's unreachable, so real IG publishing can't work.
        # Local dev simulates instead (even for genuinely connected accounts).
        # TikTok pushes the bytes itself, so it stays real everywhere.
        if real and platform == "instagram" and settings.API_BASE_URL.startswith("http://localhost"):
            real = False
        if real:
            # Roll the token if it's near expiry before using it.
            from ..routers.socials import maybe_refresh_token

            maybe_refresh_token(db, account)
            if account.status != "connected":
                return _fail(db, pub, f"Your {platform.title()} session expired — reconnect the account and retry (it's free).")
            pub.status = "uploading"
            db.commit()
            try:
                if platform == "tiktok":
                    _publish_tiktok(db, pub)
                elif platform == "youtube":
                    _publish_youtube(db, pub)
                else:
                    _real_publish(db, pub)
            except httpx.HTTPError:
                _fail(db, pub, f"Could not reach {platform.title()}. Check your connection and retry — it's free.")
        else:
            _mock_publish(db, pub)
    finally:
        db.close()


def start_publish(publish_id: uuid.UUID) -> None:
    threading.Thread(target=_run_publish, args=(publish_id,), daemon=True).start()
