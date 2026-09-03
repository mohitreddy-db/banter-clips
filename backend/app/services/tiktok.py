"""TikTok Login Kit + Content Posting API primitives (BR-13).

Token endpoints, user info, refresh, and the Direct Post upload flow. The
OAuth route handlers live in routers/socials.py and the publish state machine
in services/publishing.py — both call down into here.

Every HTTP call to TikTok goes through client(), which optionally rides an
HTTP forward proxy (TIKTOK_PROXY_URL). TikTok is ISP-blocked in India and
geo-sensitive about where API traffic originates, so pointing that at a US
box makes the integration work the same from the Bangalore droplet, local
dev, or anywhere else. The one TikTok URL that must NOT be proxied is the
authorize page — that opens in the user's own browser.
"""

from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings

AUTHORIZE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
API = "https://open.tiktokapis.com/v2"

# Refresh when the 24h access token is inside its last 2 hours. The refresh
# token itself lasts a year, so any account touched at least yearly survives.
REFRESH_WINDOW = timedelta(hours=2)

# TikTok chunk rules: every chunk 5–64 MB except the final one, which may
# absorb the remainder. Clips are 10–30s (~14 MB) so almost always 1 chunk.
MAX_SINGLE_CHUNK = 64_000_000
CHUNK_SIZE = 32_000_000


def configured() -> bool:
    return bool(
        settings.TIKTOK_CLIENT_KEY
        and settings.TIKTOK_CLIENT_SECRET
        and settings.TIKTOK_REDIRECT_URI
    )


def client(timeout: float = 20) -> httpx.Client:
    """An httpx client for TikTok traffic — proxied through the US box when
    TIKTOK_PROXY_URL is set, direct otherwise."""
    return httpx.Client(proxy=settings.TIKTOK_PROXY_URL or None, timeout=timeout)


def exchange_code(code: str) -> dict:
    """Authorization code → access token (24h) + refresh token (365d)."""
    with client() as c:
        return c.post(
            TOKEN,
            data={
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.TIKTOK_REDIRECT_URI,
            },
        ).json()


def fetch_user(token: str) -> dict:
    """Who authorized us. Only user.info.basic fields — username/bio need the
    user.info.profile scope, which we don't request."""
    with client() as c:
        body = c.get(
            f"{API}/user/info/",
            params={"fields": "open_id,union_id,avatar_url,display_name"},
            headers={"Authorization": f"Bearer {token}"},
        ).json()
    return (body.get("data") or {}).get("user") or {}


def maybe_refresh_token(db, account) -> None:
    """Roll the 24h access token via the year-long refresh token when it is
    near (or past) expiry. Same contract as the Instagram refresher: quiet on
    transient failure, flips the account to revoked only when the token is
    dead and unrefreshable."""
    if (
        account.status != "connected"
        or not account.refresh_token
        or account.token_expires_at is None
        or account.token_expires_at - datetime.now(timezone.utc) > REFRESH_WINDOW
    ):
        return
    try:
        with client() as c:
            body = c.post(
                TOKEN,
                data={
                    "client_key": settings.TIKTOK_CLIENT_KEY,
                    "client_secret": settings.TIKTOK_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": account.refresh_token,
                },
            ).json()
    except httpx.HTTPError:
        return  # transient — retry on the next touch
    if "access_token" in body:
        account.access_token = body["access_token"]
        # TikTok rotates refresh tokens; always store the newest one.
        account.refresh_token = body.get("refresh_token", account.refresh_token)
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=body.get("expires_in", 86400)
        )
        db.commit()
    elif account.token_expires_at < datetime.now(timezone.utc):
        account.status = "revoked"
        account.revoked_at = datetime.now(timezone.utc)
        db.commit()


# ── Direct Post (Content Posting API) ───────────────────────────────────

# Every viewership level TikTok defines, most public first. `creator_info`
# returns the subset this creator may actually use right now (a private
# account, for instance, never offers PUBLIC_TO_EVERYONE), and the composer
# renders exactly that subset — TikTok's UX guidelines require the choice to
# come from the creator, not from us.
PRIVACY_LEVELS = (
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
)

# Human labels, matching TikTok's own composer wording.
PRIVACY_LABELS = {
    "PUBLIC_TO_EVERYONE": "Everyone",
    "MUTUAL_FOLLOW_FRIENDS": "Friends",
    "FOLLOWER_OF_CREATOR": "Followers",
    "SELF_ONLY": "Only me",
}


def creator_info(token: str) -> dict:
    """Pre-publish check TikTok requires: who's posting, what privacy levels
    their account allows right now, which interactions their settings permit,
    and how long a video they may post.

    The audit treats calling this before every publish as mandatory — the
    composer must be built from this response rather than from assumptions.
    """
    with client() as c:
        body = c.post(
            f"{API}/post/publish/creator_info/query/",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
    return body


def error_of(body: dict) -> str | None:
    """TikTok's error message when a response carries one, else None.
    Every endpoint uses the same `error: {code, message}` envelope and signals
    success with code "ok"."""
    error = body.get("error") or {}
    code = error.get("code")
    if code in (None, "ok"):
        return None
    return error.get("message") or code


def creator_profile(token: str) -> dict:
    """`creator_info` normalised for the composer.

    Raises RuntimeError with TikTok's own message when the query fails, so the
    caller can show the creator what TikTok said rather than a generic error.
    """
    body = creator_info(token)
    message = error_of(body)
    if message:
        raise RuntimeError(message)
    data = body.get("data") or {}
    options = [p for p in PRIVACY_LEVELS if p in (data.get("privacy_level_options") or [])]
    return {
        "nickname": data.get("creator_nickname") or "",
        "username": data.get("creator_username") or "",
        "avatar_url": data.get("creator_avatar_url") or "",
        "privacy_level_options": options,
        "comment_disabled": bool(data.get("comment_disabled")),
        "duet_disabled": bool(data.get("duet_disabled")),
        "stitch_disabled": bool(data.get("stitch_disabled")),
        "max_video_post_duration_sec": data.get("max_video_post_duration_sec") or 0,
    }


def post_init(
    token: str,
    *,
    caption: str,
    privacy: str,
    video_size: int,
    allow_comment: bool = False,
    allow_duet: bool = False,
    allow_stitch: bool = False,
    brand_organic: bool = False,
    branded_content: bool = False,
) -> dict:
    """Start a Direct Post via FILE_UPLOAD — we push the bytes rather than
    have TikTok pull a URL, so no domain verification is needed and local
    dev can genuinely publish to the sandbox.

    Every field here mirrors a control the creator actually saw: the privacy
    level they picked, the interactions they allowed, and whether they
    disclosed the video as commercial content. `is_aigc` is the one we set
    ourselves — every BanterClips video is AI-generated, and TikTok policy
    requires that label whether or not the creator thinks about it.
    """
    if video_size <= MAX_SINGLE_CHUNK:
        chunk_size, chunk_count = video_size, 1
    else:
        chunk_size, chunk_count = CHUNK_SIZE, video_size // CHUNK_SIZE
    with client() as c:
        return c.post(
            f"{API}/post/publish/video/init/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "post_info": {
                    "title": caption[:2200],
                    "privacy_level": privacy,
                    # TikTok's fields are negative ("disable_x"); the composer
                    # asks the positive question, so invert here once.
                    "disable_comment": not allow_comment,
                    "disable_duet": not allow_duet,
                    "disable_stitch": not allow_stitch,
                    # Commercial content disclosure. brand_organic = "Your
                    # brand" (Promotional content label), brand_content =
                    # "Branded content" (Paid partnership label).
                    "brand_organic_toggle": brand_organic,
                    "brand_content_toggle": branded_content,
                    "is_aigc": True,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": chunk_count,
                },
            },
        ).json()


def upload_video(upload_url: str, data: bytes) -> None:
    """PUT the bytes to TikTok's upload URL. Chunked only past 64 MB; the
    final chunk absorbs the floor-division remainder per TikTok's rules."""
    total = len(data)
    if total <= MAX_SINGLE_CHUNK:
        ranges = [(0, total - 1)]
    else:
        count = total // CHUNK_SIZE
        ranges = [
            (i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE - 1 if i < count - 1 else total - 1)
            for i in range(count)
        ]
    with client(timeout=300) as c:
        for start, end in ranges:
            r = c.put(
                upload_url,
                content=data[start : end + 1],
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start}-{end}/{total}",
                },
            )
            r.raise_for_status()


def post_status(token: str, publish_id: str) -> dict:
    with client() as c:
        return c.post(
            f"{API}/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {token}"},
            json={"publish_id": publish_id},
        ).json()
