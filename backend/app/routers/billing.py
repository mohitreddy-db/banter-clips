"""Plan changes (BR-15). Stripe Checkout replaces `upgrade` before launch —
the webhook will land on the same two mutations (set plan / set
cancel_at_period_end), so the API shape is stable.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import User
from ..schemas import PlanChangeResponse

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/upgrade", response_model=PlanChangeResponse)
def upgrade(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.plan = "creator"
    user.cancel_at_period_end = False
    user.plan_renews_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()
    record_event(db, "upgrade_completed", user)
    return PlanChangeResponse(
        plan="creator",
        cancel_at_period_end=False,
        message="Welcome to Creator — downloads and watermark-free publishing are unlocked.",
    )


@router.post("/cancel", response_model=PlanChangeResponse)
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # BR-09/BR-15: downgrades apply at period end; videos are never deleted.
    user.cancel_at_period_end = True
    db.commit()
    record_event(db, "plan_cancelled", user)
    return PlanChangeResponse(
        plan=user.plan,
        cancel_at_period_end=True,
        message="Creator stays active until the end of the billing period.",
    )
