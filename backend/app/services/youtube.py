"""YouTube OAuth and Shorts upload primitives, using the existing HTTP client."""

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import update

from ..config import settings
from ..models import Publish

AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
REVOKE = "https://oauth2.googleapis.com/revoke"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REFRESH_WINDOW = timedelta(minutes=5)


def configured() -> bool:
    return bool(settings.YOUTUBE_CLIENT_ID and settings.YOUTUBE_CLIENT_SECRET and settings.YOUTUBE_REDIRECT_URI)


def exchange_code(code: str) -> dict:
    return httpx.post(
        TOKEN,
        data={
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.YOUTUBE_REDIRECT_URI,
        },
        timeout=20,
    ).json()


def delete_stored_api_data(db, account_id) -> None:
    """Delete data returned by YouTube while retaining BanterClips history.

    The upload response gives us a YouTube video id, which is embedded in the
    publish row's external URL. Title, description, visibility, timestamps,
    and status are BanterClips/user-authored data; the URL is the only API Data
    we retain from ``videos.insert``.
    """
    db.execute(
        update(Publish)
        .where(Publish.social_account_id == account_id)
        .values(external_url=None)
    )


def _expire_invalid_grant(db, account) -> None:
    account.status = "revoked"
    account.revoked_at = datetime.now(timezone.utc)
    account.access_token = None
    account.refresh_token = None
    account.platform_user_id = None
    account.token_expires_at = None
    delete_stored_api_data(db, account.id)
    db.commit()


def maybe_refresh_token(db, account) -> None:
    """Refresh a near-expiry grant and purge data if Google revoked it.

    Transport/server errors are transient and get retried on the next account
    read, publish, or scheduled housekeeping pass. ``invalid_grant`` is
    definitive: the user revoked access (or the grant expired), so all stored
    credentials and YouTube-returned API Data are deleted immediately.
    """
    if (
        account.status != "connected"
        or account.token_expires_at is None
        or account.token_expires_at - datetime.now(timezone.utc) > REFRESH_WINDOW
    ):
        return
    if not account.refresh_token:
        _expire_invalid_grant(db, account)
        return
    try:
        response = httpx.post(
            TOKEN,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": account.refresh_token,
            },
            timeout=20,
        )
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return
    if response.is_success and "access_token" in body:
        account.access_token = body["access_token"]
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.get("expires_in", 3600))
        db.commit()
    elif body.get("error") == "invalid_grant":
        _expire_invalid_grant(db, account)


def upload_short(
    token: str,
    video: bytes,
    *,
    title: str,
    description: str,
    privacy_status: str,
) -> str:
    """Create a resumable session, then upload these small clips in one PUT."""
    headers = {"Authorization": f"Bearer {token}"}
    init = httpx.post(
        UPLOAD,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            **headers,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(len(video)),
            "X-Upload-Content-Type": "video/mp4",
        },
        json={
            "snippet": {"title": title, "description": description, "categoryId": "17"},
            "status": {
                "privacyStatus": privacy_status,
                # Every BanterClips render is AI-generated. The made-for-kids
                # value is intentionally omitted rather than guessed for the
                # creator; YouTube applies the channel's own audience setting.
                "containsSyntheticMedia": True,
            },
        },
        timeout=30,
    )
    init.raise_for_status()
    upload_url = init.headers.get("location")
    if not upload_url:
        raise httpx.HTTPError("YouTube did not return an upload URL")
    uploaded = httpx.put(
        upload_url,
        headers={**headers, "Content-Type": "video/mp4", "Content-Length": str(len(video))},
        content=video,
        timeout=300,
    )
    uploaded.raise_for_status()
    video_id = uploaded.json().get("id")
    if not video_id:
        raise httpx.HTTPError("YouTube did not return a video id")
    return video_id


def revoke(token: str) -> bool:
    """Tell Google the grant is over, retrying transient failures immediately.

    A 200 response means Google revoked the grant. A 400 means the token is
    already invalid, which is also the desired terminal state. Local deletion
    is never blocked on an outage, but short transient failures get three
    attempts before the caller removes its copy of the credential.
    """
    for _ in range(3):
        try:
            response = httpx.post(REVOKE, data={"token": token}, timeout=10)
            if response.status_code in (200, 400):
                return True
            if response.status_code < 500 and response.status_code != 429:
                return False
        except httpx.HTTPError:
            continue
    return False
