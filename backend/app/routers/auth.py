"""Magic-link auth (BR-02). No passwords.

POST /auth/request-link  → creates the account if new, issues a one-time token.
                           DEV_MODE returns the token in the response; in
                           production it is emailed and never returned.
POST /auth/verify        → exchanges a valid token for a 30-day session JWT.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import record_event
from ..models import LoginToken, User, UserPreferences
from ..schemas import MagicLinkRequest, MagicLinkResponse, SessionResponse, UserOut, VerifyRequest
from ..security import create_session_jwt, hash_token, login_token_expiry, new_login_token
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-link", response_model=MagicLinkResponse)
def request_link(body: MagicLinkRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, display_name=body.display_name or email.split("@")[0])
        user.preferences = UserPreferences()
        db.add(user)
        db.commit()
        record_event(db, "account_created", user)

    raw, digest = new_login_token()
    db.add(LoginToken(user_id=user.id, token_hash=digest, expires_at=login_token_expiry()))
    db.commit()

    # Production: email `raw` as a link, return {"sent": true} only.
    return MagicLinkResponse(sent=True, dev_token=raw if settings.DEV_MODE else None)


@router.post("/verify", response_model=SessionResponse)
def verify(body: VerifyRequest, db: Session = Depends(get_db)):
    token = db.scalar(select(LoginToken).where(LoginToken.token_hash == hash_token(body.token)))
    now = datetime.now(timezone.utc)
    if token is None or token.used_at is not None or token.expires_at < now:
        raise HTTPException(401, "This sign-in link is invalid or has expired.")
    token.used_at = now

    user = db.get(User, token.user_id)
    user.last_login_at = now
    db.commit()
    record_event(db, "signed_in", user)

    return SessionResponse(access_token=create_session_jwt(user.id), user=UserOut.model_validate(user))
