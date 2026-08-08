"""Client-side analytics events (BR-11) — landing CTA clicks, preview plays,
pricing views. Server-side events are recorded directly in the other routers.
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import bearer
from ..models import Event, User
from ..schemas import EventIn
from ..security import decode_session_jwt

router = APIRouter(prefix="/events", tags=["analytics"])

ALLOWED = {
    "landing_cta_clicked",
    "preview_played",
    "pricing_viewed",
    "onboarding_step_completed",
    "onboarding_step_skipped",
    "upgrade_started",
}


@router.post("", status_code=202)
def track(
    body: EventIn,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    if body.name not in ALLOWED:
        return {"ok": False}
    user_id = decode_session_jwt(creds.credentials) if creds else None
    if user_id is not None and db.get(User, user_id) is None:
        user_id = None
    db.add(Event(user_id=user_id, name=body.name, props=body.props))
    db.commit()
    return {"ok": True}
