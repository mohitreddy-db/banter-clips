"""Public feedback — anyone can leave a note; admins read them all.

No sign-in required: a visitor who bounced off the landing page is exactly
who we want to hear from. When a valid session is presented the note is
attached to the account; otherwise the optional email is all we keep.
Spam is kept out by a honeypot field and a per-IP hourly cap.
"""

import logging
import threading
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_optional_user
from ..models import FEEDBACK_CATEGORIES, Feedback, User

log = logging.getLogger("banter.feedback")

router = APIRouter(prefix="/feedback", tags=["feedback"])

RATE_LIMIT = 10        # notes
RATE_WINDOW = 3600     # per IP, per hour
_recent: dict[str, deque] = {}
_lock = threading.Lock()


def _allowed(ip: str) -> bool:
    now = time.time()
    with _lock:
        q = _recent.setdefault(ip, deque())
        while q and q[0] < now - RATE_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return False
        q.append(now)
        return True


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "?"


class FeedbackIn(BaseModel):
    message: str = Field(min_length=5, max_length=2000)
    category: Literal[FEEDBACK_CATEGORIES] = "other"  # type: ignore[valid-type]
    rating: int | None = Field(default=None, ge=1, le=5)
    email: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, max_length=80)
    page: str = Field(default="", max_length=200)
    # Honeypot: real forms leave it empty; bots fill every field they see.
    website: str = Field(default="", max_length=200)


def submit(db: Session, body: FeedbackIn, user: User | None,
           ip: str, user_agent: str) -> Feedback | None:
    """Store one note. Returns None when it was silently dropped (honeypot)."""
    if body.website.strip():
        return None
    if not _allowed(ip):
        raise HTTPException(429, "That's a lot of feedback at once — try again in a bit.")
    row = Feedback(
        user_id=user.id if user else None,
        email=(user.email if user else (body.email or "").strip() or None),
        name=((user.display_name if user else None) or (body.name or "").strip() or None),
        category=body.category,
        rating=body.rating,
        message=body.message.strip(),
        page=body.page.strip()[:200],
        user_agent=(user_agent or "")[:300],
    )
    db.add(row)
    db.commit()
    return row


@router.post("", status_code=201)
def leave_feedback(
    body: FeedbackIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    row = submit(db, body, user, _client_ip(request), request.headers.get("user-agent", ""))
    # A honeypot hit gets the same happy answer a real note gets.
    return {"ok": True, "id": str(row.id) if row else None}
