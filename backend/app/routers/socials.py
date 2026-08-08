"""Social account connections (BR-13).

Instagram is the beta launch platform. The real platform OAuth app is still in
review, so `connect` is a mock that immediately returns a connected account —
but the resource model, revocation, and one-account-per-platform rule are the
real ones. When OAuth approval lands, `connect` becomes a redirect to the
platform's consent screen and a callback fills in the same row.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import SocialAccount, User
from ..schemas import SocialAccountOut, SocialConnectRequest

router = APIRouter(prefix="/socials", tags=["socials"])

# One platform at MVP launch (BR-13); the rest are visible but locked.
CONNECTABLE = {"instagram"}


@router.get("", response_model=list[SocialAccountOut])
def list_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(SocialAccount)
        .where(SocialAccount.user_id == user.id, SocialAccount.status == "connected")
        .order_by(SocialAccount.connected_at)
    ).all()


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
