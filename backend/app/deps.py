from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Clip, Event, User
from .security import decode_session_jwt

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_session_jwt(creds.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account no longer exists")
    return user


def month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def successful_clips_this_month(db: Session, user: User) -> int:
    """BR-09: only successful videos count against the allowance.

    Failures are free because they never reach "ready". Demo runs ([mock])
    also reach "ready" but produce the sample video, so they are excluded
    too — charging for a clip the user cannot publish would be indefensible.
    """
    return db.scalar(
        select(func.count())
        .select_from(Clip)
        .where(
            Clip.user_id == user.id,
            Clip.status == "ready",
            Clip.is_simulated.is_(False),
            Clip.completed_at >= month_start(),
        )
    )


def usage_for(db: Session, user: User) -> dict:
    limit = settings.PLAN_LIMITS.get(user.plan, 5)
    used = successful_clips_this_month(db, user)
    return {
        "plan": user.plan,
        "used": used,
        "limit": limit,
        "left": max(0, limit - used),
        # Client non-negotiables: Free = publish-only + watermark;
        # Creator = download + watermark-free.
        "can_download": user.plan == "creator",
        "watermarked": user.plan != "creator",
    }


def record_event(db: Session, name: str, user: User | None = None, **props) -> None:
    """BR-11 product analytics — server-side event log, no dashboard."""
    db.add(Event(user_id=user.id if user else None, name=name, props=props))
    db.commit()
