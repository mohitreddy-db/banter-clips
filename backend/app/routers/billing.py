"""Plan changes (BR-15) — Stripe Checkout + webhooks.

Design principles (payments are delicate):
- **Stripe is the ledger.** We never mirror invoices/charges locally; the DB
  stores only the derived entitlement (users.plan + subscription pointers)
  and an audit log of processed webhook deliveries (stripe_events).
- **Webhooks are triggers, not truth.** Stripe delivers at-least-once and in
  any order, so handlers never trust event payloads for state: every billing
  event triggers a fetch of the customer's CURRENT subscriptions from the
  Stripe API and convergence to that. Replays and reordering are harmless.
- **Idempotent transitions.** Analytics events fire only on actual plan
  transitions; processed deliveries are recorded for audit/debugging.
- **One live subscription per user.** If a checkout race ever produces two,
  the sync cancels all but the newest (prevents double billing).

Dev fallback — with STRIPE_* env unset, /billing/checkout returns 503
{code: stripe_not_configured} and the frontend uses the mock /billing/upgrade.
"""

from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import StripeEvent, User
from ..schemas import PlanChangeResponse

router = APIRouter(prefix="/billing", tags=["billing"])

ACTIVE_STATUSES = ("active", "trialing", "past_due")  # past_due = grace period

BILLING_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_CREATOR)


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _g(obj, key, default=None):
    """StripeObject supports [key] but not .get() (stripe-python v15)."""
    try:
        value = obj[key]
    except (KeyError, TypeError, IndexError):
        return default
    return default if value is None else value


def _period_end(subscription) -> datetime | None:
    """current_period_end lives on the sub (older API) or its items (newer)."""
    ts = _g(subscription, "current_period_end")
    if not ts:
        items = _g(_g(subscription, "items", {}), "data", [])
        ts = _g(items[0], "current_period_end") if items else None
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def _ensure_customer(db: Session, user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = _stripe().Customer.create(
        email=user.email,
        name=user.display_name or None,
        metadata={"banterclips_user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def sync_subscription_state(db: Session, user: User) -> None:
    """Converge local plan state to Stripe's current truth for this customer."""
    if not (stripe_configured() and user.stripe_customer_id):
        return
    subs = _stripe().Subscription.list(customer=user.stripe_customer_id, status="all", limit=20)
    live = [s for s in _g(subs, "data", []) if _g(s, "status") in ACTIVE_STATUSES]

    # Safety net: a user must never hold two live subscriptions.
    if len(live) > 1:
        live.sort(key=lambda s: _g(s, "created", 0), reverse=True)
        for extra in live[1:]:
            try:
                _stripe().Subscription.cancel(_g(extra, "id"))
                record_event(db, "duplicate_subscription_cancelled", user, subscription=_g(extra, "id"))
            except stripe.StripeError:
                pass  # next sync retries; worst case support cancels manually
        live = live[:1]

    current = live[0] if live else None
    was_creator = user.plan == "creator"

    if current is not None:
        user.plan = "creator"
        user.stripe_subscription_id = _g(current, "id")
        user.cancel_at_period_end = bool(_g(current, "cancel_at_period_end"))
        user.plan_renews_at = _period_end(current)
    else:
        user.plan = "free"
        user.stripe_subscription_id = None
        user.cancel_at_period_end = False
        user.plan_renews_at = None
    db.commit()

    # Analytics only on real transitions — replay-safe.
    if not was_creator and user.plan == "creator":
        record_event(db, "upgrade_completed", user, provider="stripe")
    elif was_creator and user.plan == "free":
        record_event(db, "plan_downgraded", user, provider="stripe")


@router.post("/checkout")
def checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not stripe_configured():
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Payments are not configured on this server."})
    # Re-check against Stripe, not just our mirror, to close drift windows.
    sync_subscription_state(db, user)
    if user.plan == "creator" and not user.cancel_at_period_end:
        raise HTTPException(409, "You're already on the Creator plan.")

    session = _stripe().checkout.Session.create(
        mode="subscription",
        customer=_ensure_customer(db, user),
        line_items=[{"price": settings.STRIPE_PRICE_CREATOR, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/account?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/pricing?checkout=cancelled",
        client_reference_id=str(user.id),
        allow_promotion_codes=True,
    )
    record_event(db, "upgrade_started", user, provider="stripe")
    return {"url": session.url}


@router.post("/portal")
def portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (stripe_configured() and user.stripe_customer_id):
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Billing portal is not available."})
    session = _stripe().billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/account",
    )
    return {"url": session.url}


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Webhook secret not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    event_id = event["id"]
    event_type = event["type"]

    # Already processed this delivery → acknowledge without side effects.
    if db.get(StripeEvent, event_id) is not None:
        return {"received": True, "duplicate": True}

    if event_type in BILLING_EVENTS:
        obj = event["data"]["object"]
        user = None
        if event_type == "checkout.session.completed":
            ref = _g(obj, "client_reference_id")
            user = db.get(User, ref) if ref else None
            if user is not None:
                # Link ids from the session, then converge from the API.
                user.stripe_customer_id = _g(obj, "customer") or user.stripe_customer_id
                db.commit()
        else:  # customer.subscription.*
            customer_id = _g(obj, "customer")
            if customer_id:
                user = db.scalar(select(User).where(User.stripe_customer_id == customer_id))
        if user is not None:
            sync_subscription_state(db, user)

    # Record AFTER successful processing: a mid-processing crash lets Stripe's
    # retry reprocess (sync is convergent, so replays are safe).
    ts = event.get("created")
    db.add(
        StripeEvent(
            id=event_id,
            type=event_type,
            event_created_at=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
        )
    )
    db.commit()
    return {"received": True}


@router.post("/upgrade", response_model=PlanChangeResponse)
def upgrade_mock(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dev-only mock upgrade — disabled once Stripe is configured."""
    if stripe_configured():
        raise HTTPException(400, "Use /billing/checkout — payments run through Stripe.")
    user.plan = "creator"
    user.cancel_at_period_end = False
    user.plan_renews_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()
    record_event(db, "upgrade_completed", user, provider="mock")
    return PlanChangeResponse(
        plan="creator",
        cancel_at_period_end=False,
        message="Welcome to Creator — downloads and watermark-free publishing are unlocked.",
    )


@router.post("/cancel", response_model=PlanChangeResponse)
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # BR-09/BR-15: downgrades apply at period end; videos are never deleted.
    if stripe_configured() and user.stripe_subscription_id:
        try:
            _stripe().Subscription.modify(user.stripe_subscription_id, cancel_at_period_end=True)
        except stripe.StripeError:
            raise HTTPException(502, "Stripe could not process the cancellation. Try again.")
        sync_subscription_state(db, user)  # mirror Stripe immediately
    else:
        user.cancel_at_period_end = True
        db.commit()
    record_event(db, "plan_cancelled", user)
    return PlanChangeResponse(
        plan=user.plan,
        cancel_at_period_end=user.cancel_at_period_end,
        message="Creator stays active until the end of the billing period.",
    )
