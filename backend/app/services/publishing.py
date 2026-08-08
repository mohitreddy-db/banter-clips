"""Publish worker (BR-13).

Two paths, chosen per connected account:
- Real: the account came from the Instagram Business Login OAuth flow →
  publish an actual Reel via the Instagram Graph API (create media container
  from a public video URL → poll processing → publish → fetch permalink).
- Mock: the account was created by the dev mock connector → simulate the
  same honest status machine without touching Instagram.
"""

import threading
import time
import uuid
from datetime import datetime, timezone

import httpx

from ..config import settings
from ..db import SessionLocal
from ..models import Publish

FAIL_MARKER = "[fail]"
MOCK_TOKEN = "mock-oauth-token"
UPLOAD_SECONDS = 2.2
IG_GRAPH = "https://graph.instagram.com/v23.0"


def _public_video_url(clip) -> str:
    # Meta downloads the video itself, so the URL must be publicly reachable
    # (the cloudflared tunnel in dev, the droplet domain in prod).
    filename = (clip.video_url or "demo.mp4").rsplit("/", 1)[-1]
    return f"{settings.API_BASE_URL}/media/{filename}"


def _fail(db, pub, message: str) -> None:
    pub.status = "failed"
    pub.error = message
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
    pub.external_url = f"https://www.instagram.com/reel/BC{str(pub.id)[:8]}/"
    db.commit()


def _run_publish(publish_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        pub = db.get(Publish, publish_id)
        if pub is None:
            return
        account = pub.account
        real = bool(account and account.access_token and account.access_token != MOCK_TOKEN and account.platform_user_id)
        if real:
            # Roll the 60-day token if it's near expiry before using it.
            from ..routers.socials import maybe_refresh_token

            maybe_refresh_token(db, account)
            if account.status != "connected":
                return _fail(db, pub, "Your Instagram session expired — reconnect the account and retry (it's free).")
            pub.status = "uploading"
            db.commit()
            try:
                _real_publish(db, pub)
            except httpx.HTTPError:
                _fail(db, pub, "Could not reach Instagram. Check your connection and retry — it's free.")
        else:
            _mock_publish(db, pub)
    finally:
        db.close()


def start_publish(publish_id: uuid.UUID) -> None:
    threading.Thread(target=_run_publish, args=(publish_id,), daemon=True).start()
