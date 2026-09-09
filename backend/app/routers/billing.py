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

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import StoreSubscription, StripeEvent, User
from ..schemas import PlanChangeResponse
from ..services import store_billing

log = logging.getLogger("banter.billing")

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


def native_stripe_configured() -> bool:
    return stripe_configured() and bool(settings.STRIPE_PUBLISHABLE_KEY)


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


@router.post("/mobile/payment-sheet")
def mobile_payment_sheet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a Stripe subscription for the native PaymentSheet.

    Card details go directly from Stripe's native SDK to Stripe. The app gets
    only short-lived client secrets; the API secret remains server-side.
    """
    if not native_stripe_configured():
        raise HTTPException(503, detail={
            "code": "stripe_not_configured",
            "message": "Native payments are not configured on this server.",
        })

    sync_subscription_state(db, user)
    if user.plan == "creator" and not user.cancel_at_period_end:
        raise HTTPException(409, "You're already on the Creator plan.")

    customer_id = _ensure_customer(db, user)
    try:
        ephemeral_key = _stripe().EphemeralKey.create(
            customer=customer_id,
            stripe_version="2025-06-30.basil",
        )
        subscription = _stripe().Subscription.create(
            customer=customer_id,
            items=[{"price": settings.STRIPE_PRICE_CREATOR}],
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"},
            metadata={"banterclips_user_id": str(user.id), "client": "mobile"},
            expand=["latest_invoice.confirmation_secret"],
        )
        invoice = _g(subscription, "latest_invoice", {})
        confirmation_secret = _g(invoice, "confirmation_secret", {})
        client_secret = _g(confirmation_secret, "client_secret")
        if not client_secret:
            client_secret = _g(_g(invoice, "payment_intent", {}), "client_secret")
        if not client_secret:
            _stripe().Subscription.cancel(_g(subscription, "id"))
            raise HTTPException(502, "Stripe did not create a payable invoice.")
    except HTTPException:
        raise
    except stripe.StripeError as exc:
        log.exception("could not create native Stripe subscription")
        raise HTTPException(502, "Stripe could not start the payment. Try again.") from exc

    record_event(db, "upgrade_started", user, provider="stripe_mobile")
    return {
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "payment_intent_client_secret": client_secret,
        "customer_id": customer_id,
        "ephemeral_key_secret": _g(ephemeral_key, "secret"),
        "subscription_id": _g(subscription, "id"),
        "test_mode": settings.STRIPE_PUBLISHABLE_KEY.startswith("pk_test_"),
    }


@router.post("/mobile/confirm")
def confirm_mobile_payment(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Converge the user's entitlement immediately after PaymentSheet closes."""
    if not stripe_configured():
        raise HTTPException(503, "Payments are not configured on this server.")
    sync_subscription_state(db, user)
    if user.plan != "creator":
        raise HTTPException(409, detail={
            "code": "payment_pending",
            "message": "Payment is still processing. Pull to refresh in a moment.",
        })
    return {"plan": user.plan}


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
    ts = _g(event, "created")
    db.add(
        StripeEvent(
            id=event_id,
            type=event_type,
            event_created_at=datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
        )
    )
    db.commit()
    return {"received": True}


# ------------------------------------------------------- store billing (app)

class StorePurchase(BaseModel):
    platform: Literal["ios", "android"]
    product_id: str = Field(max_length=128)
    # Google: the purchase token. iOS: the base64 receipt, kept only as a
    # fallback — `transaction_id` is what the App Store Server API needs.
    purchase_token: str = Field(max_length=8192)
    transaction_id: str | None = Field(default=None, max_length=128)


def sync_store_subscription(db: Session, user: User, sub: StoreSubscription) -> None:
    """Re-ask the store about one subscription and converge to its answer.

    The mirror of `sync_subscription_state` on the Stripe path, and it obeys
    the same rule: the store is the truth, this only derives from it.
    """
    try:
        entitlement = store_billing.verify(
            sub.platform,
            purchase_token=sub.purchase_token,
            product_id=sub.product_id,
            transaction_id=sub.purchase_token if sub.platform == "ios" else None,
        )
    except store_billing.StoreError:
        # The store could not be reached. Leave the entitlement exactly as it
        # is: an outage at Apple must never downgrade a paying customer.
        log.warning("could not re-verify store subscription %s", sub.id)
        return
    _apply_entitlement(db, user, sub, entitlement)


def _apply_entitlement(
    db: Session, user: User, sub: StoreSubscription, entitlement: store_billing.Entitlement
) -> None:
    was_creator = user.plan == "creator"

    sub.status = entitlement.status
    sub.expires_at = entitlement.expires_at
    sub.auto_renewing = entitlement.auto_renewing
    sub.last_verified_at = datetime.now(timezone.utc)

    if entitlement.is_entitled:
        user.plan = "creator"
        user.plan_renews_at = entitlement.expires_at
        user.cancel_at_period_end = not entitlement.auto_renewing
    else:
        # Only drop the plan if nothing ELSE is paying for it. A user who
        # bought on the web and then also on their phone must not be
        # downgraded because the phone subscription lapsed.
        if not (stripe_configured() and user.stripe_subscription_id):
            user.plan = "free"
            user.plan_renews_at = None
            user.cancel_at_period_end = False
    db.commit()

    if not was_creator and user.plan == "creator":
        record_event(db, "upgrade_completed", user, provider=sub.platform)
    elif was_creator and user.plan == "free":
        record_event(db, "plan_downgraded", user, provider=sub.platform)


def refresh_expired_store_plan(db: Session, user: User) -> None:
    """Downgrade a store subscription that has run out.

    Cheap by construction: the expiry the store gave us is stored locally, so
    this is a date comparison and touches the network only for a subscription
    that has actually lapsed. Called from `/me/usage`, which every client
    reads before it gates anything.

    This is the safety net that makes the entitlement self-healing without
    server-to-server notifications. Once Google RTDN and Apple ASSN are wired
    up, a lapse will be visible within minutes instead of at the next read —
    but this should stay regardless, because notifications get dropped.
    """
    if user.plan != "creator":
        return
    sub = db.scalar(
        select(StoreSubscription)
        .where(StoreSubscription.user_id == user.id)
        .order_by(StoreSubscription.expires_at.desc().nullslast())
    )
    if sub is None or sub.expires_at is None:
        return
    if sub.expires_at > datetime.now(timezone.utc):
        return  # still paid for — no call, no cost
    sync_store_subscription(db, user, sub)


@router.post("/mobile/verify", response_model=PlanChangeResponse)
def verify_store_purchase(
    body: StorePurchase,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a store receipt and grant Creator if it checks out.

    This is the ONLY way a mobile purchase becomes an entitlement. The client
    telling us a purchase succeeded is a request to go and ask Apple or
    Google, never an answer in itself — the app is on someone else's device
    and can be patched.

    Idempotent: keyed on the store's own purchase token, so the app can (and
    does) retry after a dropped connection without double-granting.
    """
    if body.product_id != settings.STORE_PRODUCT_CREATOR:
        raise HTTPException(
            400,
            detail={
                "code": "unknown_store_product",
                "message": "That store product is not a BanterClips Creator subscription.",
            },
        )

    if not store_billing.configured(body.platform):
        raise HTTPException(
            503,
            detail={
                "code": "store_not_configured",
                "message": "In-app purchases are not configured on this server.",
            },
        )

    try:
        entitlement = store_billing.verify(
            body.platform,
            purchase_token=body.purchase_token,
            product_id=body.product_id,
            transaction_id=body.transaction_id,
        )
    except store_billing.StoreError as exc:
        # Our problem, not theirs — and the money may already be taken, so the
        # message must not suggest the purchase failed.
        log.warning("store verification failed for user %s: %s", user.id, exc)
        raise HTTPException(
            502,
            detail={
                "code": "store_unreachable",
                "message": "We couldn't confirm the purchase with the store. "
                "It will apply automatically — reopen the app in a minute.",
            },
        )

    if not entitlement.is_entitled:
        raise HTTPException(
            400,
            detail={
                "code": "purchase_not_active",
                "message": "That subscription is no longer active.",
            },
        )

    if entitlement.product_id != settings.STORE_PRODUCT_CREATOR:
        raise HTTPException(
            400,
            detail={
                "code": "wrong_store_product",
                "message": "The verified purchase is not for the Creator subscription.",
            },
        )

    sub = db.scalar(
        select(StoreSubscription).where(
            StoreSubscription.purchase_token == entitlement.purchase_token
        )
    )
    if sub is None:
        sub = StoreSubscription(
            user_id=user.id,
            platform=body.platform,
            product_id=entitlement.product_id,
            purchase_token=entitlement.purchase_token,
        )
        db.add(sub)
    elif sub.user_id != user.id:
        # This receipt already entitles a different account. One paid
        # subscription, one account — otherwise a receipt could be passed
        # around to unlock Creator for everybody who has it.
        record_event(db, "store_receipt_reuse_blocked", user, platform=body.platform)
        raise HTTPException(
            409,
            detail={
                "code": "receipt_already_used",
                "message": "That purchase is already linked to another "
                "BanterClips account.",
            },
        )

    _apply_entitlement(db, user, sub, entitlement)

    return PlanChangeResponse(
        plan=user.plan,
        cancel_at_period_end=user.cancel_at_period_end,
        message="Welcome to Creator — downloads and watermark-free publishing are unlocked.",
    )


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
    # A store subscription can only be cancelled from the store — neither
    # Apple nor Google exposes an API for it, by design. Setting our own flag
    # would be worse than useless: the customer would see "cancelled" here and
    # keep being charged. Say where to go instead.
    store_sub = db.scalar(
        select(StoreSubscription).where(
            StoreSubscription.user_id == user.id,
            StoreSubscription.status.in_(("active", "cancelled")),
        )
    )
    if store_sub is not None and not (stripe_configured() and user.stripe_subscription_id):
        raise HTTPException(
            409,
            detail={
                "code": "cancel_in_store",
                "message": "This subscription is billed by "
                f"{'Apple' if store_sub.platform == 'ios' else 'Google'}. "
                "Cancel it in your store subscription settings — your videos "
                "are never deleted.",
            },
        )

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
