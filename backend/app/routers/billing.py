"""Plan changes (BR-15) — web Stripe plus native/store subscriptions.

Design principles (payments are delicate):
- **Each provider is its own ledger.** Stripe, Apple and Google state is kept
  independently; users.plan is derived as the OR of active sources.
- **Stripe is the web-payment ledger.** We never mirror invoices/charges locally;
  the DB stores derived subscription state and an audit log of webhook deliveries.
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, record_event
from ..models import Event, StripeEvent, User
from ..schemas import PlanChangeResponse
from ..services import entitlements, store_billing

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


def _customer_exists(customer_id: str) -> bool:
    """False when Stripe does not know the id in the CURRENT mode — the
    normal case for a customer created under live keys once the server is
    on sandbox keys (or the reverse). Such an id is stale, not an error."""
    try:
        _stripe().Customer.retrieve(customer_id)
        return True
    except stripe.InvalidRequestError:
        return False


def _forget_stale_customer(db: Session, user: User) -> None:
    log.warning("user %s: stripe customer %s does not exist in this mode; clearing",
                user.id, user.stripe_customer_id)
    user.stripe_customer_id = None
    user.stripe_subscription_id = None
    user.stripe_subscription_status = None
    user.stripe_current_period_end = None
    user.stripe_cancel_at_period_end = False
    user.stripe_mobile_pending_subscription_id = None
    # Clearing stale Stripe state must not clear a valid Apple/Google plan.
    entitlements.reconcile_user_entitlements(db, user, event_provider="stripe")


def _ensure_customer(db: Session, user: User) -> str:
    if user.stripe_customer_id:
        if _customer_exists(user.stripe_customer_id):
            return user.stripe_customer_id
        _forget_stale_customer(db, user)
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
    try:
        subs = _stripe().Subscription.list(customer=user.stripe_customer_id, status="all", limit=20)
    except stripe.InvalidRequestError:
        # The id belongs to the other Stripe mode: no subscription can exist
        # for it here. Forget it so the next checkout creates a fresh one.
        _forget_stale_customer(db, user)
        return
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
    if current is not None:
        user.stripe_subscription_id = _g(current, "id")
        user.stripe_subscription_status = _g(current, "status")
        user.stripe_cancel_at_period_end = bool(_g(current, "cancel_at_period_end"))
        user.stripe_current_period_end = _period_end(current)
        user.stripe_mobile_pending_subscription_id = None
    else:
        user.stripe_subscription_id = None
        user.stripe_subscription_status = None
        user.stripe_cancel_at_period_end = False
        user.stripe_current_period_end = None

    # Stripe owns only its source fields. Shared access is the OR of Stripe and
    # every verified store source, so one provider can never clobber another.
    entitlements.reconcile_user_entitlements(db, user, event_provider="stripe")


@router.post("/checkout")
def checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not stripe_configured():
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Payments are not configured on this server."})
    # Re-check against Stripe, not just our mirror, to close drift windows.
    sync_subscription_state(db, user)
    if user.plan == "creator":
        providers = entitlements.active_providers(db, user)
        billed_by = ", ".join(providers) if providers else "an existing entitlement"
        raise HTTPException(409, f"You're already on the Creator plan through {billed_by}.")

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


@router.get("/packs")
def packs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The top-up menu — available to every plan (PRICING §6). Free users
    top up too; packs buy fuel, never capabilities."""
    from ..services import credits

    return {"packs": credits.prices(db)["packs"],
            "available": bool(settings.STRIPE_SECRET_KEY)}


class TopupBody(BaseModel):
    pack: str


@router.post("/topup")
def topup(body: TopupBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """One-time Stripe Checkout for a credit pack. Credits are granted by the
    webhook when the payment completes — never on redirect, which is spoofable."""
    from ..services import credits

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Payments are not configured on this server."})
    chosen = credits.pack(db, body.pack)
    if chosen is None:
        raise HTTPException(404, "Unknown credit pack.")
    session = _stripe().checkout.Session.create(
        mode="payment",
        customer=_ensure_customer(db, user),
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "usd",
                "unit_amount": int(chosen["usd"] * 100),
                "product_data": {"name": f"BanterClips — {chosen['credits']:,} credits"},
            },
        }],
        success_url=f"{settings.FRONTEND_URL}/account?topup=success",
        cancel_url=f"{settings.FRONTEND_URL}/account?topup=cancelled",
        client_reference_id=str(user.id),
        metadata={"kind": "topup", "user_id": str(user.id),
                  "credits": str(chosen["credits"]), "pack": chosen["key"]},
    )
    record_event(db, "topup_started", user, pack=chosen["key"], credits=chosen["credits"])
    return {"url": session.url}


# ------------------------------------------------ native Stripe PaymentSheet

class MobilePaymentSheetBody(BaseModel):
    # The app persists one request id for one checkout attempt and reuses it on
    # network retries. It becomes Stripe's idempotency key.
    request_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


def _lock_billing_user(db: Session, user: User) -> User:
    """Serialize payment starts for one account at the database boundary."""
    return db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _mobile_client_secret(subscription) -> str | None:
    invoice = _g(subscription, "latest_invoice", {})
    confirmation = _g(invoice, "confirmation_secret", {})
    return _g(confirmation, "client_secret") or _g(
        _g(invoice, "payment_intent", {}), "client_secret"
    )


def _pending_mobile_subscription(customer_id: str, user: User):
    """Reuse one pending native subscription and cancel accidental extras."""
    if user.stripe_mobile_pending_subscription_id:
        try:
            saved = _stripe().Subscription.retrieve(
                user.stripe_mobile_pending_subscription_id,
                expand=["latest_invoice.confirmation_secret"],
            )
        except stripe.InvalidRequestError:
            user.stripe_mobile_pending_subscription_id = None
        else:
            metadata = _g(saved, "metadata", {}) or {}
            if (
                _g(saved, "status") == "incomplete"
                and _g(metadata, "client") == "mobile"
                and _g(metadata, "banterclips_user_id") == str(user.id)
            ):
                return saved
            user.stripe_mobile_pending_subscription_id = None

    subscriptions = _stripe().Subscription.list(customer=customer_id, status="all", limit=20)
    pending = []
    for subscription in _g(subscriptions, "data", []):
        metadata = _g(subscription, "metadata", {}) or {}
        if (
            _g(subscription, "status") == "incomplete"
            and _g(metadata, "client") == "mobile"
            and _g(metadata, "banterclips_user_id") == str(user.id)
        ):
            pending.append(subscription)
    pending.sort(key=lambda item: _g(item, "created", 0), reverse=True)
    for extra in pending[1:]:
        try:
            _stripe().Subscription.cancel(_g(extra, "id"))
        except stripe.StripeError:
            log.warning("could not cancel duplicate pending subscription %s", _g(extra, "id"))
    if not pending:
        return None
    return _stripe().Subscription.retrieve(
        _g(pending[0], "id"), expand=["latest_invoice.confirmation_secret"]
    )


@router.post("/mobile/payment-sheet")
def mobile_payment_sheet(
    body: MobilePaymentSheetBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or resume a Stripe subscription for native PaymentSheet.

    App Store and Google Play builds should use their required in-app purchase
    SDKs plus ``/mobile/verify`` for digital Creator access. This endpoint is
    for distributions where native Stripe billing is permitted.
    """
    if not native_stripe_configured():
        raise HTTPException(
            503,
            detail={
                "code": "stripe_not_configured",
                "message": "Native Stripe payments are not configured on this server.",
            },
        )

    try:
        sync_subscription_state(db, user)
    except stripe.StripeError as exc:
        raise HTTPException(502, "Stripe could not refresh billing. Try again.") from exc
    if user.plan == "creator":
        raise HTTPException(409, "You're already on the Creator plan.")

    created = False
    try:
        # Lock once before customer creation (which may commit), then reacquire
        # before subscription creation. Concurrent requests cannot both pass
        # the pending-subscription check while holding this row lock.
        locked_user = _lock_billing_user(db, user)
        customer_id = _ensure_customer(db, locked_user)
        locked_user = _lock_billing_user(db, user)

        subscription = _pending_mobile_subscription(customer_id, locked_user)
        client_secret = _mobile_client_secret(subscription) if subscription is not None else None
        if subscription is not None and not client_secret:
            _stripe().Subscription.cancel(_g(subscription, "id"))
            locked_user.stripe_mobile_pending_subscription_id = None
            subscription = None

        if subscription is None:
            subscription = _stripe().Subscription.create(
                customer=customer_id,
                items=[{"price": settings.STRIPE_PRICE_CREATOR}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                metadata={"banterclips_user_id": str(user.id), "client": "mobile"},
                expand=["latest_invoice.confirmation_secret"],
                idempotency_key=f"banter-mobile-sub:{user.id}:{body.request_id}",
            )
            created = True
            client_secret = _mobile_client_secret(subscription)
        if not client_secret:
            _stripe().Subscription.cancel(_g(subscription, "id"))
            locked_user.stripe_mobile_pending_subscription_id = None
            raise HTTPException(502, "Stripe did not create a payable invoice.")

        locked_user.stripe_mobile_pending_subscription_id = _g(subscription, "id")
        db.commit()
        ephemeral_key = _stripe().EphemeralKey.create(
            customer=customer_id,
            stripe_version=settings.STRIPE_MOBILE_API_VERSION,
        )
    except HTTPException:
        db.rollback()
        raise
    except stripe.StripeError as exc:
        db.rollback()
        log.exception("could not create or resume native Stripe subscription")
        raise HTTPException(502, "Stripe could not start the payment. Try again.") from exc

    if created:
        record_event(db, "upgrade_started", user, provider="stripe_mobile")
    return {
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "payment_intent_client_secret": client_secret,
        "customer_id": customer_id,
        "ephemeral_key_secret": _g(ephemeral_key, "secret"),
        "subscription_id": _g(subscription, "id"),
        "test_mode": settings.STRIPE_PUBLISHABLE_KEY.startswith("pk_test_"),
        "reused": not created,
    }


@router.post("/mobile/confirm")
def confirm_mobile_payment(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Converge Creator access immediately after PaymentSheet completes."""
    if not stripe_configured():
        raise HTTPException(503, "Payments are not configured on this server.")
    try:
        sync_subscription_state(db, user)
    except stripe.StripeError as exc:
        raise HTTPException(502, "Stripe could not refresh billing. Try again.") from exc
    if not entitlements.stripe_is_active(user):
        raise HTTPException(
            409,
            detail={
                "code": "payment_pending",
                "message": "Payment is still processing. Pull to refresh in a moment.",
            },
        )
    return {"plan": user.plan}


@router.post("/portal")
def portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (stripe_configured() and user.stripe_customer_id):
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Billing portal is not available."})
    if not _customer_exists(user.stripe_customer_id):
        _forget_stale_customer(db, user)
        raise HTTPException(503, detail={"code": "stripe_not_configured", "message": "Billing portal is not available until your next checkout."})
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
            meta = _g(obj, "metadata") or {}
            if user is not None and _g(obj, "mode") == "payment" and _g(meta, "kind") == "topup":
                # A credit pack. Idempotent: the StripeEvent dedupe above
                # guarantees this delivery grants exactly once.
                from ..services import credits as credit_svc

                amount = int(_g(meta, "credits") or 0)
                if amount > 0 and _g(obj, "payment_status") == "paid":
                    # Claim the Stripe event before moving the wallet, then
                    # commit marker + credit ledger together. Concurrent
                    # deliveries cannot double-grant the same paid pack.
                    ts = _g(event, "created")
                    db.add(
                        StripeEvent(
                            id=event_id,
                            type=event_type,
                            event_created_at=(
                                datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
                            ),
                        )
                    )
                    try:
                        db.flush()
                    except IntegrityError:
                        db.rollback()
                        return {"received": True, "duplicate": True}
                    credit_svc.apply(
                        db,
                        user,
                        amount,
                        "topup",
                        note=f"pack {_g(meta, 'pack', '?')}",
                        commit=False,
                    )
                    db.add(
                        Event(
                            user_id=user.id,
                            name="topup_completed",
                            props={"pack": _g(meta, "pack"), "credits": amount},
                        )
                    )
                    db.commit()
                    return {"received": True}
                user = None  # not a subscription — skip the sync below
            elif user is not None:
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


# ----------------------------------------------- Apple / Google subscriptions

class StorePurchaseBody(BaseModel):
    platform: Literal["ios", "android"]
    product_id: str = Field(min_length=1, max_length=128)
    # Android requires the purchase token. Apple uses transaction_id; an
    # optional receipt may still be sent by older clients but is never trusted.
    purchase_token: str | None = Field(default=None, max_length=16384)
    transaction_id: str | None = Field(default=None, max_length=128)


@router.post("/mobile/verify", response_model=PlanChangeResponse)
def verify_store_purchase(
    body: StorePurchaseBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify an Apple/Google subscription and apply Creator to the account."""
    if body.product_id != settings.STORE_PRODUCT_CREATOR:
        raise HTTPException(
            400,
            detail={
                "code": "unknown_store_product",
                "message": "That store product is not a BanterClips Creator subscription.",
            },
        )
    if body.platform == "android" and not body.purchase_token:
        raise HTTPException(400, detail={"code": "purchase_token_required"})
    if body.platform == "ios" and not body.transaction_id:
        raise HTTPException(400, detail={"code": "transaction_id_required"})
    if not store_billing.configured(body.platform):
        raise HTTPException(
            503,
            detail={
                "code": "store_not_configured",
                "message": "In-app purchases are not configured on this server.",
            },
        )

    try:
        verified = store_billing.verify(
            body.platform,
            purchase_token=body.purchase_token or body.transaction_id or "",
            product_id=body.product_id,
            transaction_id=body.transaction_id,
        )
    except store_billing.StoreError as exc:
        log.warning("store verification failed for user %s: %s", user.id, exc)
        raise HTTPException(
            502,
            detail={
                "code": "store_unreachable",
                "message": "We couldn't confirm the purchase with the store. "
                "Your purchase is safe; retry or restore purchases in a moment.",
            },
        ) from exc

    if verified.account_token != str(user.id):
        record_event(db, "store_account_token_mismatch", user, platform=body.platform)
        raise HTTPException(
            409,
            detail={
                "code": "purchase_account_mismatch",
                "message": "This purchase was not created for the signed-in BanterClips account.",
            },
        )
    if verified.product_id != settings.STORE_PRODUCT_CREATOR:
        raise HTTPException(
            400,
            detail={
                "code": "wrong_store_product",
                "message": "The verified purchase is not for the Creator subscription.",
            },
        )
    if not verified.is_entitled:
        raise HTTPException(
            400,
            detail={
                "code": "purchase_not_active",
                "message": "That subscription is no longer active.",
            },
        )

    try:
        entitlements.apply_store_purchase(db, user, body.platform, verified)
    except entitlements.ReceiptAlreadyUsed as exc:
        db.rollback()
        record_event(db, "store_receipt_reuse_blocked", user, platform=body.platform)
        raise HTTPException(
            409,
            detail={
                "code": "receipt_already_used",
                "message": "That purchase is already linked to another BanterClips account.",
            },
        ) from exc

    return PlanChangeResponse(
        plan=user.plan,
        cancel_at_period_end=user.cancel_at_period_end,
        message="Welcome to Creator — access is unlocked on mobile and web.",
    )


@router.get("/status")
def billing_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Combined billing state for clients deciding which purchase UI to show."""
    return {
        "plan": user.plan,
        "providers": entitlements.active_providers(db, user),
        "renews_at": user.plan_renews_at,
        "cancel_at_period_end": user.cancel_at_period_end,
    }


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
    # A Stripe subscription is cancelled here. Store subscriptions must be
    # cancelled in Apple/Google settings; pretending otherwise would leave the
    # customer being charged after our UI said cancellation succeeded.
    if stripe_configured() and user.stripe_subscription_id:
        try:
            _stripe().Subscription.modify(
                user.stripe_subscription_id, cancel_at_period_end=True
            )
        except stripe.InvalidRequestError as exc:
            _forget_stale_customer(db, user)
            raise HTTPException(
                409,
                detail={
                    "code": "stripe_subscription_not_found",
                    "message": "That Stripe subscription no longer exists. Billing state was refreshed.",
                },
            ) from exc
        except stripe.StripeError as exc:
            raise HTTPException(
                502, "Stripe could not process the cancellation. Try again."
            ) from exc
        else:
            sync_subscription_state(db, user)
            record_event(db, "plan_cancelled", user, provider="stripe")
            providers = entitlements.active_providers(db, user)
            message = "Creator stays active until the end of the billing period."
            if any(provider in ("ios", "android") for provider in providers):
                message = "Stripe is cancelled; Creator remains active through your app store."
            return PlanChangeResponse(
                plan=user.plan,
                cancel_at_period_end=user.cancel_at_period_end,
                message=message,
            )

    store_providers = [
        provider for provider in entitlements.active_providers(db, user)
        if provider in ("ios", "android")
    ]
    if store_providers:
        store_name = "Apple" if store_providers[0] == "ios" else "Google Play"
        raise HTTPException(
            409,
            detail={
                "code": "cancel_in_store",
                "message": f"This subscription is billed by {store_name}. "
                "Cancel it in your store subscription settings.",
            },
        )

    # Dev-only mock entitlement.
    user.cancel_at_period_end = True
    db.commit()
    record_event(db, "plan_cancelled", user, provider="mock")
    return PlanChangeResponse(
        plan=user.plan,
        cancel_at_period_end=user.cancel_at_period_end,
        message="Creator stays active until the end of the billing period.",
    )
