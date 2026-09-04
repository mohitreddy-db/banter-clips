"""YouTube OAuth and Shorts upload primitives, using the existing HTTP client."""

from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings

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


def maybe_refresh_token(db, account) -> None:
    if (
        account.status != "connected"
        or not account.refresh_token
        or account.token_expires_at is None
        or account.token_expires_at - datetime.now(timezone.utc) > REFRESH_WINDOW
    ):
        return
    try:
        body = httpx.post(
            TOKEN,
            data={
                "client_id": settings.YOUTUBE_CLIENT_ID,
                "client_secret": settings.YOUTUBE_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": account.refresh_token,
            },
            timeout=20,
        ).json()
    except httpx.HTTPError:
        return
    if "access_token" in body:
        account.access_token = body["access_token"]
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=body.get("expires_in", 3600))
        db.commit()
    elif account.token_expires_at < datetime.now(timezone.utc):
        account.status = "revoked"
        account.revoked_at = datetime.now(timezone.utc)
        db.commit()


def metadata(caption: str, fallback: str) -> tuple[str, str]:
    text = (caption or fallback).strip()
    first, _, rest = text.partition("\n")
    return first[:100] or fallback[:100], (rest.strip() or text)[:5000]


def upload_short(token: str, video: bytes, *, title: str, description: str) -> str:
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
                "privacyStatus": settings.YOUTUBE_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
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


def revoke(token: str) -> None:
    """Tell Google the grant is over.

    Deleting our copy of a token does not end the user's authorization — it
    stays listed under their Google Account until it expires, and the YouTube
    API Services Developer Policies require an API client to revoke it when the
    user disconnects. Revoking either token ends the whole grant, so callers
    pass the refresh token when they have one.

    Best-effort: a disconnect must succeed even if Google is unreachable, and
    a token Google no longer recognises returns 400, which is the outcome we
    wanted anyway.
    """
    try:
        httpx.post(REVOKE, data={"token": token}, timeout=10)
    except httpx.HTTPError:
        pass
