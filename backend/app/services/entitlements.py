"""Provider-neutral Creator entitlement reconciliation.

Stripe, Apple and Google each own their own subscription state. ``users.plan``
is only a compatibility cache derived from those independent sources; no
provider is allowed to downgrade a user while another provider remains active.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Event, StoreSubscription, User
from . import store_billing

log = logging.getLogger("banter.entitlements")

STRIPE_ACTIVE_STATUSES = ("active", "trialing", "past_due")
STORE_ACTIVE_STATUSES = ("active", "cancelled")
STORE_RETRY_DELAY = timedelta(minutes=5)


class ReceiptAlreadyUsed(Exception):
    """A verified store subscription is linked to another BanterClips user."""


class PurchaseAccountMismatch(Exception):
    """The store's app account token does not match the authenticated user."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def stripe_is_active(user: User) -> bool:
    if not user.stripe_subscription_id:
        return False
    # Deployment migration backfills legacy subscription pointers to active;
    # after that, unknown/null state must not grant access indefinitely.
    return user.stripe_subscription_status in STRIPE_ACTIVE_STATUSES


def active_store_subscriptions(
    db: Session, user: User, *, at: datetime | None = None
) -> list[StoreSubscription]:
    at = at or _now()
    return list(
        db.scalars(
            select(StoreSubscription).where(
                StoreSubscription.user_id == user.id,
                StoreSubscription.product_id == settings.STORE_PRODUCT_CREATOR,
                StoreSubscription.status.in_(STORE_ACTIVE_STATUSES),
                StoreSubscription.expires_at.is_not(None),
                StoreSubscription.expires_at > at,
            )
        )
    )


def active_providers(db: Session, user: User) -> list[str]:
    providers: list[str] = []
    if stripe_is_active(user):
        providers.append("stripe")
    providers.extend(sub.platform for sub in active_store_subscriptions(db, user))
    return list(dict.fromkeys(providers))


def reconcile_user_entitlements(
    db: Session,
    user: User,
    *,
    event_provider: str = "billing",
    allow_downgrade: bool = True,
) -> None:
    """Derive the shared plan from every locally verified billing source."""
    now = _now()
    stores = active_store_subscriptions(db, user, at=now)
    stripe_active = stripe_is_active(user)
    was_creator = user.plan == "creator"
    entitled = stripe_active or bool(stores)

    # A temporary provider outage during expiry verification must not cut off a
    # paying account. The caller schedules a short retry and keeps the last
    # known combined state until the store can answer.
    if was_creator and not entitled and not allow_downgrade:
        db.commit()
        return

    if entitled:
        user.plan = "creator"
        expiries = [sub.expires_at for sub in stores if sub.expires_at is not None]
        if stripe_active and user.stripe_current_period_end is not None:
            expiries.append(user.stripe_current_period_end)
        user.plan_renews_at = max(expiries) if expiries else None

        renewing_sources: list[bool] = [sub.auto_renewing for sub in stores]
        if stripe_active:
            renewing_sources.append(not user.stripe_cancel_at_period_end)
        user.cancel_at_period_end = bool(renewing_sources) and not any(renewing_sources)
    else:
        user.plan = "free"
        user.plan_renews_at = None
        user.cancel_at_period_end = False

    if not was_creator and user.plan == "creator":
        db.add(Event(user_id=user.id, name="upgrade_completed", props={"provider": event_provider}))
    elif was_creator and user.plan == "free":
        db.add(Event(user_id=user.id, name="plan_downgraded", props={"provider": event_provider}))
    db.commit()


def _next_regular_verification(now: datetime, expires_at: datetime | None) -> datetime:
    scheduled = now + timedelta(hours=max(settings.STORE_REVERIFY_HOURS, 1))
    if expires_at is not None and expires_at > now:
        return min(scheduled, expires_at)
    return scheduled


def apply_store_purchase(
    db: Session,
    user: User,
    platform: str,
    entitlement: store_billing.Entitlement,
) -> StoreSubscription:
    """Atomically link a verified store subscription and recompute access."""
    user_id = user.id
    if entitlement.account_token != str(user_id):
        raise PurchaseAccountMismatch

    sub = db.scalar(
        select(StoreSubscription).where(
            StoreSubscription.platform == platform,
            StoreSubscription.purchase_token == entitlement.purchase_token,
        )
    )
    if sub is not None and sub.user_id != user_id:
        raise ReceiptAlreadyUsed

    # Google returns this when a plan change replaces an older purchase token.
    # The successor must stay with the account that owned its predecessor.
    predecessor = None
    if entitlement.linked_purchase_token:
        predecessor = db.scalar(
            select(StoreSubscription).where(
                StoreSubscription.platform == platform,
                StoreSubscription.purchase_token == entitlement.linked_purchase_token,
            )
        )
        if predecessor is not None and predecessor.user_id != user_id:
            raise ReceiptAlreadyUsed

    if sub is None:
        sub = StoreSubscription(
            user_id=user_id,
            platform=platform,
            product_id=entitlement.product_id,
            purchase_token=entitlement.purchase_token,
        )
        db.add(sub)
        try:
            db.flush()
        except IntegrityError:
            # Two client retries may race. The database uniqueness constraint is
            # the final authority; reload the winner and return its state.
            db.rollback()
            sub = db.scalar(
                select(StoreSubscription).where(
                    StoreSubscription.platform == platform,
                    StoreSubscription.purchase_token == entitlement.purchase_token,
                )
            )
            if sub is None or sub.user_id != user_id:
                raise ReceiptAlreadyUsed

    if predecessor is not None and predecessor.id != sub.id:
        predecessor.status = "expired"
        predecessor.auto_renewing = False

    now = _now()
    sub.product_id = entitlement.product_id
    sub.status = entitlement.status
    sub.expires_at = entitlement.expires_at
    sub.auto_renewing = entitlement.auto_renewing
    sub.last_verified_at = now
    sub.next_verification_at = _next_regular_verification(now, entitlement.expires_at)
    # SessionLocal disables autoflush; reconciliation must see this new source.
    db.flush()
    reconcile_user_entitlements(db, user, event_provider=platform)
    return sub


def refresh_store_entitlements(db: Session, user: User) -> None:
    """Reverify due store sources without making every API request a store call.

    Called during authentication. Most requests perform only one indexed local
    query. A network check happens at stored expiry or at the configured
    periodic interval, whichever comes first.
    """
    now = _now()
    subscriptions = list(
        db.scalars(
            select(StoreSubscription).where(
                StoreSubscription.user_id == user.id,
                StoreSubscription.status.in_(STORE_ACTIVE_STATUSES),
            )
        )
    )
    due = [
        sub
        for sub in subscriptions
        if sub.next_verification_at <= now
        or (sub.expires_at is not None and sub.expires_at <= now)
    ]
    if not due:
        return

    changed = False
    verification_failed = False
    preserve_for_outage = False
    event_provider = "store"
    for sub in due:
        event_provider = sub.platform
        try:
            result = store_billing.verify(
                sub.platform,
                purchase_token=sub.purchase_token,
                product_id=sub.product_id,
                transaction_id=sub.purchase_token if sub.platform == "ios" else None,
            )
        except store_billing.StoreError as exc:
            verification_failed = True
            sub.next_verification_at = now + STORE_RETRY_DELAY
            if sub.expires_at is not None:
                outage_deadline = sub.expires_at + timedelta(
                    hours=max(settings.STORE_OUTAGE_GRACE_HOURS, 0)
                )
                preserve_for_outage = preserve_for_outage or now < outage_deadline
            log.warning("could not reverify store subscription %s: %s", sub.id, exc)
            continue
        except Exception:
            verification_failed = True
            sub.next_verification_at = now + STORE_RETRY_DELAY
            if sub.expires_at is not None:
                outage_deadline = sub.expires_at + timedelta(
                    hours=max(settings.STORE_OUTAGE_GRACE_HOURS, 0)
                )
                preserve_for_outage = preserve_for_outage or now < outage_deadline
            log.exception("unexpected store verification failure for %s", sub.id)
            continue

        if result.account_token != str(user.id):
            log.error(
                "store subscription %s account token no longer matches user %s",
                sub.id,
                user.id,
            )
            sub.status = "expired"
            sub.auto_renewing = False
            sub.last_verified_at = now
            sub.next_verification_at = _next_regular_verification(now, result.expires_at)
            db.add(
                Event(
                    user_id=user.id,
                    name="store_account_token_mismatch",
                    props={"provider": sub.platform},
                )
            )
            changed = True
            continue

        sub.product_id = result.product_id
        sub.status = (
            result.status
            if result.product_id == settings.STORE_PRODUCT_CREATOR
            else "expired"
        )
        sub.expires_at = result.expires_at
        sub.auto_renewing = (
            result.auto_renewing
            if result.product_id == settings.STORE_PRODUCT_CREATOR
            else False
        )
        sub.last_verified_at = now
        sub.next_verification_at = _next_regular_verification(now, result.expires_at)
        changed = True

    if changed or verification_failed:
        # SessionLocal disables autoflush; reconciliation must read updates made
        # by the verification loop, including expiry/revocation.
        db.flush()
        reconcile_user_entitlements(
            db,
            user,
            event_provider=event_provider,
            allow_downgrade=not preserve_for_outage,
        )
