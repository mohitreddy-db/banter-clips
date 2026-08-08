from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, record_event, usage_for
from ..models import User, UserPreferences
from ..schemas import PreferencesOut, PreferencesUpdate, UsageOut, UserOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/usage", response_model=UsageOut)
def usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return usage_for(db, user)


@router.patch("/preferences", response_model=PreferencesOut)
def update_preferences(
    body: PreferencesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = user.preferences
    if prefs is None:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(prefs, field, value)
    db.commit()

    if data.get("onboarding_completed"):
        record_event(db, "onboarding_completed", user, role=prefs.role, sports=prefs.sports)
    return prefs
