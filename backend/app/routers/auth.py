"""Auth (BR-02).

Production path — Supabase Auth:
  The frontend signs up / signs in against Supabase (email+password with real
  verification emails, or magic link). It then POSTs the Supabase access token
  to /auth/supabase; we verify it against the Supabase Auth server, find or
  create the local user row, and issue our own 30-day session JWT. Everything
  downstream (clips, plans, socials) only ever sees our session.

Dev path — /auth/request-link + /auth/verify:
  Instant magic-link sign-in with the token returned in the response. Only
  mounted when DEV_MODE=true; returns 404 in production.
"""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import record_event
from ..models import LoginToken, User, UserPreferences
from ..schemas import MagicLinkRequest, MagicLinkResponse, SessionResponse, UserOut, VerifyRequest
from ..security import create_session_jwt, hash_token, login_token_expiry, new_login_token

router = APIRouter(prefix="/auth", tags=["auth"])


class SupabaseExchangeRequest(BaseModel):
    access_token: str


def _find_or_create_user(db: Session, *, email: str, supabase_uid: str | None, display_name: str | None) -> User:
    user = None
    if supabase_uid:
        user = db.scalar(select(User).where(User.supabase_uid == supabase_uid))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, supabase_uid=supabase_uid, display_name=display_name or email.split("@")[0])
        user.preferences = UserPreferences()
        db.add(user)
        db.commit()
        record_event(db, "account_created", user)
        # Welcome credits (PRICING §5): one-time, enough for one 15s video.
        from ..services import credits

        credits.grant_signup(db, user)
    elif supabase_uid and user.supabase_uid != supabase_uid:
        user.supabase_uid = supabase_uid
        db.commit()
    return user


@router.post("/supabase", response_model=SessionResponse)
def supabase_exchange(body: SupabaseExchangeRequest, db: Session = Depends(get_db)):
    if not settings.SUPABASE_URL:
        raise HTTPException(503, "Supabase auth is not configured on this server.")

    # Ask the Supabase Auth server who this token belongs to.
    try:
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {body.access_token}",
            },
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the auth server. Try again.")
    if resp.status_code != 200:
        raise HTTPException(401, "Invalid or expired sign-in. Please sign in again.")

    info = resp.json()
    email = (info.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(401, "This account has no email address.")

    meta = info.get("user_metadata") or {}
    user = _find_or_create_user(
        db,
        email=email,
        supabase_uid=info.get("id"),
        display_name=meta.get("display_name") or meta.get("full_name"),
    )
    if user.is_blocked:
        # Deliberately IDENTICAL to the bad-token response above: a blocked
        # account is never told it is blocked — the sign-in simply never
        # sticks and the app lands back on the login page.
        raise HTTPException(401, "Invalid or expired sign-in. Please sign in again.")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    record_event(db, "signed_in", user, provider="supabase")

    return SessionResponse(access_token=create_session_jwt(user.id), user=UserOut.model_validate(user))


# ---------------------------------------------------------------- dev-only ---

def _dev_only():
    if not settings.DEV_MODE:
        raise HTTPException(404, "Not found")


@router.post("/request-link", response_model=MagicLinkResponse)
def request_link(body: MagicLinkRequest, db: Session = Depends(get_db)):
    _dev_only()
    email = body.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=body.display_name or email.split("@")[0])
        user.preferences = UserPreferences()
        db.add(user)
        db.commit()
        record_event(db, "account_created", user)
        # Welcome credits (PRICING §5): one-time, enough for one 15s video.
        from ..services import credits

        credits.grant_signup(db, user)

    raw, digest = new_login_token()
    db.add(LoginToken(user_id=user.id, token_hash=digest, expires_at=login_token_expiry()))
    db.commit()
    return MagicLinkResponse(sent=True, dev_token=raw)


@router.post("/verify", response_model=SessionResponse)
def verify(body: VerifyRequest, db: Session = Depends(get_db)):
    _dev_only()
    token = db.scalar(select(LoginToken).where(LoginToken.token_hash == hash_token(body.token)))
    now = datetime.now(timezone.utc)
    if token is None or token.used_at is not None or token.expires_at < now:
        raise HTTPException(401, "This sign-in link is invalid or has expired.")
    token.used_at = now

    user = db.get(User, token.user_id)
    if user is None or user.is_blocked:
        # Same wording as a spent link — a blocked account learns nothing.
        raise HTTPException(401, "This sign-in link is invalid or has expired.")
    user.last_login_at = now
    db.commit()
    record_event(db, "signed_in", user, provider="dev-link")

    return SessionResponse(access_token=create_session_jwt(user.id), user=UserOut.model_validate(user))
