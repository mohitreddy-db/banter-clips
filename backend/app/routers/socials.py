"""Social account connections (BR-13).

Instagram is the beta launch platform. The real platform OAuth app is still in
review, so `connect` is a mock that immediately returns a connected account —
but the resource model, revocation, and one-account-per-platform rule are the
real ones. When OAuth approval lands, `connect` becomes a redirect to the
platform's consent screen and a callback fills in the same row.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import SocialAccount, User
from ..schemas import SocialAccountOut, SocialConnectRequest

router = APIRouter(prefix="/socials", tags=["socials"])

# One platform at MVP launch (BR-13); the rest are visible but locked.
CONNECTABLE = {"instagram"}

IG_AUTHORIZE = "https://www.instagram.com/oauth/authorize"
IG_TOKEN = "https://api.instagram.com/oauth/access_token"
IG_GRAPH = "https://graph.instagram.com"
IG_SCOPES = "instagram_business_basic,instagram_business_content_publish"

ig_oauth_configured = lambda: bool(settings.META_APP_ID and settings.META_APP_SECRET and settings.IG_REDIRECT_URI)  # noqa: E731

MOCK_TOKEN = "mock-oauth-token"
REFRESH_WINDOW = timedelta(days=15)


def maybe_refresh_token(db: Session, account: SocialAccount) -> None:
    """Instagram long-lived tokens last ~60 days and do NOT renew themselves.
    When one is inside its last 15 days, roll it via ig_refresh_token (allowed
    once the token is >24h old). Called on every /socials read and before each
    real publish, so any account used at least once in two months never lapses."""
    if (
        account.status != "connected"
        or not account.access_token
        or account.access_token == MOCK_TOKEN
        or account.token_expires_at is None
        or account.token_expires_at - datetime.now(timezone.utc) > REFRESH_WINDOW
    ):
        return
    try:
        body = httpx.get(
            f"{IG_GRAPH}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": account.access_token},
            timeout=15,
        ).json()
    except httpx.HTTPError:
        return  # transient — retry on the next touch
    if "access_token" in body:
        account.access_token = body["access_token"]
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=body.get("expires_in", 60 * 24 * 3600)
        )
        db.commit()
    elif account.token_expires_at < datetime.now(timezone.utc):
        # Expired and unrefreshable — surface as disconnected so the UI
        # prompts a clean reconnect instead of failing publishes.
        account.status = "revoked"
        account.revoked_at = datetime.now(timezone.utc)
        db.commit()


def _upsert_account(db: Session, user_id, *, handle: str, token: str, platform_user_id: str | None, expires_in: int | None = None) -> SocialAccount:
    account = db.scalar(
        select(SocialAccount).where(
            SocialAccount.user_id == user_id, SocialAccount.platform == "instagram"
        )
    )
    if account is None:
        account = SocialAccount(user_id=user_id, platform="instagram", handle=handle)
        db.add(account)
    account.handle = handle
    account.access_token = token
    account.platform_user_id = platform_user_id
    account.token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None
    )
    account.status = "connected"
    account.revoked_at = None
    db.commit()
    return account


@router.get("/instagram/oauth-url")
def instagram_oauth_url(
    next: str = "/account",
    user: User = Depends(get_current_user),
):
    """Real Instagram Business Login (BR-13). Returns the Meta consent URL;
    503 when the Meta app isn't configured so the client can fall back to the
    mock connector."""
    if not ig_oauth_configured():
        raise HTTPException(503, detail={"code": "oauth_not_configured", "message": "Instagram OAuth is not configured."})
    state = pyjwt.encode(
        {
            "sub": str(user.id),
            "purpose": "ig_oauth",
            "next": next if next.startswith("/") else "/account",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    query = urlencode(
        {
            "client_id": settings.META_APP_ID,
            "redirect_uri": settings.IG_REDIRECT_URI,
            "response_type": "code",
            "scope": IG_SCOPES,
            "state": state,
        }
    )
    return {"url": f"{IG_AUTHORIZE}?{query}"}


@router.get("/instagram/callback")
def instagram_callback(
    code: str | None = None,
    state: str = "",
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    """OAuth redirect target. Exchanges the code for a long-lived token, stores
    the real account, and bounces the browser back to the frontend."""

    def bounce(next_path: str, **params) -> RedirectResponse:
        return RedirectResponse(f"{settings.FRONTEND_URL}{next_path}?{urlencode(params)}")

    try:
        claims = pyjwt.decode(state, settings.JWT_SECRET, algorithms=["HS256"])
        assert claims.get("purpose") == "ig_oauth"
        user_id = claims["sub"]
        next_path = claims.get("next", "/account")
    except Exception:
        return bounce("/account", ig="error", reason="invalid_state")

    if error or not code:
        return bounce(next_path, ig="denied", reason=error_description or error or "cancelled")

    try:
        # 1. authorization code → short-lived token
        tok = httpx.post(
            IG_TOKEN,
            data={
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "grant_type": "authorization_code",
                "redirect_uri": settings.IG_REDIRECT_URI,
                "code": code,
            },
            timeout=15,
        ).json()
        short_token = tok["access_token"]

        # 2. short-lived → long-lived (60 days, refreshable)
        long_tok = httpx.get(
            f"{IG_GRAPH}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": settings.META_APP_SECRET,
                "access_token": short_token,
            },
            timeout=15,
        ).json()
        token = long_tok.get("access_token", short_token)
        expires_in = long_tok.get("expires_in")

        # 3. who is this?
        me = httpx.get(
            f"{IG_GRAPH}/v23.0/me",
            params={"fields": "user_id,username,account_type", "access_token": token},
            timeout=15,
        ).json()
        username = me.get("username") or "connected"
        ig_user_id = str(me.get("user_id") or tok.get("user_id") or "")
    except Exception:
        return bounce(next_path, ig="error", reason="token_exchange_failed")

    user = db.get(User, user_id)
    if user is None:
        return bounce(next_path, ig="error", reason="unknown_user")

    _upsert_account(db, user.id, handle=f"@{username}", token=token, platform_user_id=ig_user_id, expires_in=expires_in)
    record_event(db, "social_connected", user, platform="instagram", real=True)
    return bounce(next_path, ig="connected", handle=username)


@router.get("", response_model=list[SocialAccountOut])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.scalars(
        select(SocialAccount)
        .where(SocialAccount.user_id == user.id, SocialAccount.status == "connected")
        .order_by(SocialAccount.connected_at)
    ).all()
    for account in accounts:
        maybe_refresh_token(db, account)
    return [a for a in accounts if a.status == "connected"]


@router.post("/connect", response_model=SocialAccountOut, status_code=201)
def connect(body: SocialConnectRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.platform not in CONNECTABLE:
        raise HTTPException(
            400,
            detail={
                "code": "platform_locked",
                "message": f"{body.platform} arrives after the beta — Instagram is the launch platform.",
            },
        )

    existing = db.scalar(
        select(SocialAccount).where(
            SocialAccount.user_id == user.id, SocialAccount.platform == body.platform
        )
    )
    handle = "@" + (user.display_name or user.email.split("@")[0]).lower().replace(" ", "")
    if existing:
        existing.status = "connected"
        existing.revoked_at = None
        existing.handle = handle
        existing.access_token = "mock-oauth-token"
        db.commit()
        account = existing
    else:
        account = SocialAccount(
            user_id=user.id, platform=body.platform, handle=handle, access_token="mock-oauth-token"
        )
        db.add(account)
        db.commit()
    record_event(db, "social_connected", user, platform=body.platform)
    return account


@router.delete("/{platform}", response_model=SocialAccountOut)
def disconnect(platform: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.scalar(
        select(SocialAccount).where(
            SocialAccount.user_id == user.id,
            SocialAccount.platform == platform,
            SocialAccount.status == "connected",
        )
    )
    if account is None:
        raise HTTPException(404, "No connected account for that platform")
    account.status = "revoked"
    account.revoked_at = datetime.now(timezone.utc)
    account.access_token = None
    db.commit()
    record_event(db, "social_disconnected", user, platform=platform)
    return account
