"""Plan changes (BR-15).

Real path — Stripe Checkout + webhooks:
  POST /billing/checkout → hosted Stripe Checkout URL for the Creator plan.
  POST /billing/webhook  → Stripe events are the source of truth for plan
                           state (upgrade on checkout completion, sync on
                           subscription updates, downgrade on deletion).
  POST /billing/cancel   → flips cancel_at_period_end on the subscription;
                           Creator stays active until the period ends.
  POST /billing/portal   → Stripe Billing Portal (payment method, invoices).

Dev fallback — when STRIPE_* env vars are unset, /billing/checkout returns
503 {code: stripe_not_configured} and the frontend uses the mock
/billing/upgrade instead (kept for local dev, disabled when Stripe is live).
"""

from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import User
from ..schemas import PlanChangeResponse

router = APIRouter(prefix="/billing", tags=["billing"])


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PRICE_CREATOR)


def _stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


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


@router.post("/checkout")
def checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not stripe_configured():
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Payments are not configured on this server."})
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
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid webhook signature")

    obj = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        user = db.get(User, _g(obj, "client_reference_id"))
        if user is not None:
            user.stripe_customer_id = _g(obj, "customer") or user.stripe_customer_id
            user.stripe_subscription_id = _g(obj, "subscription")
            user.plan = "creator"
            user.cancel_at_period_end = False
            db.commit()
            record_event(db, "upgrade_completed", user, provider="stripe")

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.created"):
        user = db.scalar(select(User).where(User.stripe_customer_id == _g(obj, "customer")))
        if user is not None:
            active = _g(obj, "status") in ("active", "trialing", "past_due")
            user.plan = "creator" if active else "free"
            user.stripe_subscription_id = _g(obj, "id")
            user.cancel_at_period_end = bool(_g(obj, "cancel_at_period_end"))
            user.plan_renews_at = _period_end(obj)
            db.commit()

    elif event["type"] == "customer.subscription.deleted":
        user = db.scalar(select(User).where(User.stripe_customer_id == _g(obj, "customer")))
        if user is not None:
            # BR-15: downgrade at period end, videos never deleted.
            user.plan = "free"
            user.stripe_subscription_id = None
            user.cancel_at_period_end = False
            db.commit()
            record_event(db, "plan_downgraded", user, provider="stripe")

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
    user.cancel_at_period_end = True
    db.commit()
    record_event(db, "plan_cancelled", user)
    return PlanChangeResponse(
        plan=user.plan,
        cancel_at_period_end=True,
        message="Creator stays active until the end of the billing period.",
    )
