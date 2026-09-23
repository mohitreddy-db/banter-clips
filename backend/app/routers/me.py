import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event, usage_for
from ..models import (
    Clip,
    CreditEntry,
    Event,
    Job,
    LoginToken,
    Publish,
    SocialAccount,
    StorePurchase,
    StoreSubscription,
    User,
    UserPreferences,
)
from ..schemas import PreferencesOut, PreferencesUpdate, UsageOut, UserOut
from ..services import storage

log = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/usage", response_model=UsageOut)
def usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Every client reads this before it gates anything, which makes it the
    # right place to notice that a store subscription has run out. It is a
    # local date comparison unless one actually has — see the docstring on
    # refresh_expired_store_plan.
    from .billing import refresh_expired_store_plan

    refresh_expired_store_plan(db, user)
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


@router.delete("", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete the account and everything belonging to it.

    App Store guideline 5.1.1(v) requires an app that lets people create an
    account to let them delete it from inside the app — a support email is
    not enough. The privacy policy already promises the same thing, so this
    is the promise made good rather than a new one.

    What it is NOT: cancelling a subscription. Only Apple or Google can do
    that, and deleting the account here does not stop a renewal — the app
    says so on the confirmation screen and points at the store.

    Rows are removed explicitly rather than left to `ON DELETE CASCADE`.
    The cascades are declared, but SQLite only honours them with
    `PRAGMA foreign_keys=ON`, and a deletion that silently half-happens on
    one engine is exactly the bug nobody notices until a user asks why their
    clips are still there.
    """
    user_id = user.id
    supabase_uid = user.supabase_uid

    # The bytes first. Dropping rows while the videos stay fetchable at their
    # URLs is the same non-deletion `delete_clip` warns about, one scale up.
    try:
        storage.get().delete_prefix(f"users/{user_id}")
    except Exception:  # noqa: BLE001 — never block a deletion on storage
        log.exception("could not remove stored media for user %s", user_id)

    clip_ids = select(Clip.id).where(Clip.user_id == user_id)
    social_ids = select(SocialAccount.id).where(SocialAccount.user_id == user_id)

    db.execute(
        delete(Publish).where(
            or_(
                Publish.clip_id.in_(clip_ids),
                Publish.social_account_id.in_(social_ids),
            )
        )
    )
    db.execute(delete(Job).where(Job.clip_id.in_(clip_ids)))
    db.execute(delete(Clip).where(Clip.user_id == user_id))
    db.execute(delete(SocialAccount).where(SocialAccount.user_id == user_id))
    db.execute(delete(StoreSubscription).where(StoreSubscription.user_id == user_id))
    db.execute(delete(StorePurchase).where(StorePurchase.user_id == user_id))
    db.execute(delete(CreditEntry).where(CreditEntry.user_id == user_id))
    db.execute(delete(LoginToken).where(LoginToken.user_id == user_id))
    db.execute(delete(UserPreferences).where(UserPreferences.user_id == user_id))

    # Analytics keeps its shape without keeping the person: the event rows
    # stay, detached from any account. `record_event` wrote one for this
    # deletion a moment ago, and it is detached along with the rest.
    record_event(db, "account_deleted", user, plan=user.plan)
    db.execute(update(Event).where(Event.user_id == user_id).values(user_id=None))

    db.delete(user)
    db.commit()

    # Last, because it is the one thing we cannot roll back and the one that
    # can fail on its own: without it the same identity signs in again and a
    # fresh, empty account is created, which is confusing but not a data
    # leak. Their data is already gone by this point.
    _delete_supabase_identity(supabase_uid)


def _delete_supabase_identity(supabase_uid: str | None) -> None:
    """Remove the sign-in identity from Supabase Auth, best effort.

    Needs the service-role key; when it is not configured (local dev, or a
    deployment using its own auth) the account row is still gone and the
    identity is simply orphaned.
    """
    url = getattr(settings, "SUPABASE_URL", "")
    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    if not (supabase_uid and url and key):
        return
    try:
        resp = httpx.delete(
            f"{url.rstrip('/')}/auth/v1/admin/users/{supabase_uid}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=10.0,
        )
        if resp.status_code >= 400 and resp.status_code != 404:
            log.warning(
                "Supabase refused to delete identity %s: %s %s",
                supabase_uid,
                resp.status_code,
                resp.text[:200],
            )
    except httpx.HTTPError:
        log.exception("could not reach Supabase to delete identity %s", supabase_uid)
