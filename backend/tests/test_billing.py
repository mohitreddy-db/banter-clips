"""Regression tests for combined web/mobile billing behavior."""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import billing  # noqa: E402
from app.services import entitlements, store_billing  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeDb:
    def __init__(self, stores=()):
        self.stores = list(stores)
        self.added = []
        self.commits = 0

    def scalars(self, _statement):
        return iter(self.stores)

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def flush(self):
        pass

    def rollback(self):
        pass


class SequencedDb(FakeDb):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)

    def scalars(self, _statement):
        return iter(self.responses.pop(0))


def user(**overrides):
    values = {
        "id": uuid.uuid4(),
        "plan": "free",
        "plan_renews_at": None,
        "cancel_at_period_end": False,
        "stripe_subscription_id": None,
        "stripe_subscription_status": None,
        "stripe_current_period_end": None,
        "stripe_cancel_at_period_end": False,
        "stripe_mobile_pending_subscription_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_existing_web_billing_routes_are_preserved():
    routes = {
        (route.path, method)
        for route in app.routes
        for method in (getattr(route, "methods", None) or [])
    }
    assert ("/billing/packs", "GET") in routes
    assert ("/billing/topup", "POST") in routes
    assert ("/billing/webhook", "POST") in routes


def test_topup_webhook_claims_event_and_credit_in_one_transaction(monkeypatch):
    from app.models import Event, StripeEvent, User
    from app.services import credits

    account = user()
    account.credits = 0

    class WebhookDb(FakeDb):
        def get(self, model, key):
            if model is StripeEvent:
                return None
            if model is User and str(key) == str(account.id):
                return account
            return None

    class FakeRequest:
        headers = {"stripe-signature": "signature"}

        async def body(self):
            return b"payload"

    event = {
        "id": "evt_topup_once",
        "type": "checkout.session.completed",
        "created": 1700000000,
        "data": {
            "object": {
                "client_reference_id": str(account.id),
                "mode": "payment",
                "payment_status": "paid",
                "metadata": {"kind": "topup", "credits": "40", "pack": "spark"},
            }
        },
    }
    calls = []
    monkeypatch.setattr(
        billing.stripe.Webhook,
        "construct_event",
        lambda payload, signature, secret: event,
    )
    monkeypatch.setattr(credits, "apply", lambda *args, **kwargs: calls.append(kwargs))
    original = settings.STRIPE_WEBHOOK_SECRET
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    db = WebhookDb()
    try:
        response = asyncio.run(billing.webhook(FakeRequest(), db))
    finally:
        settings.STRIPE_WEBHOOK_SECRET = original

    assert response == {"received": True}
    assert calls == [{"note": "pack spark", "commit": False}]
    assert any(isinstance(value, StripeEvent) for value in db.added)
    assert any(isinstance(value, Event) for value in db.added)
    assert db.commits == 1


def test_store_and_stripe_are_combined_instead_of_clobbering_each_other():
    now = datetime.now(timezone.utc)
    store = SimpleNamespace(
        platform="ios", status="active", expires_at=now + timedelta(days=10), auto_renewing=True
    )
    account = user(
        stripe_subscription_id=None,
        stripe_subscription_status=None,
        plan="free",
    )
    db = FakeDb([store])

    entitlements.reconcile_user_entitlements(db, account, event_provider="ios")

    assert account.plan == "creator"
    assert account.plan_renews_at == store.expires_at
    assert account.cancel_at_period_end is False


def test_stripe_sync_with_no_live_sub_does_not_clobber_active_store(monkeypatch):
    now = datetime.now(timezone.utc)
    store = SimpleNamespace(
        platform="android",
        status="active",
        expires_at=now + timedelta(days=15),
        auto_renewing=True,
    )
    account = user(
        plan="creator",
        stripe_customer_id="cus_old",
        stripe_subscription_id="sub_old",
        stripe_subscription_status="active",
    )
    db = FakeDb([store])

    class Subscription:
        @staticmethod
        def list(**kwargs):
            return {"data": []}

    monkeypatch.setattr(billing, "stripe_configured", lambda: True)
    monkeypatch.setattr(billing, "_stripe", lambda: SimpleNamespace(Subscription=Subscription))
    billing.sync_subscription_state(db, account)

    assert account.stripe_subscription_id is None
    assert account.plan == "creator"
    assert account.plan_renews_at == store.expires_at


def test_active_stripe_keeps_creator_when_no_store_source_is_active():
    renews = datetime.now(timezone.utc) + timedelta(days=20)
    account = user(
        plan="creator",
        stripe_subscription_id="sub_live",
        stripe_subscription_status="active",
        stripe_current_period_end=renews,
    )
    db = FakeDb()

    entitlements.reconcile_user_entitlements(db, account, event_provider="store")

    assert account.plan == "creator"
    assert account.plan_renews_at == renews


def test_store_purchase_must_be_bound_to_authenticated_account():
    account = user()
    verified = store_billing.Entitlement(
        purchase_token="token",
        product_id="creator_monthly",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        auto_renewing=True,
        status="active",
        account_token="another-user",
    )

    with pytest.raises(entitlements.PurchaseAccountMismatch):
        entitlements.apply_store_purchase(FakeDb(), account, "android", verified)


def test_temporary_store_outage_does_not_downgrade_last_known_creator():
    account = user(plan="creator")
    db = FakeDb()

    entitlements.reconcile_user_entitlements(
        db, account, event_provider="ios", allow_downgrade=False
    )

    assert account.plan == "creator"


def test_store_outage_grace_is_bounded(monkeypatch):
    now = datetime.now(timezone.utc)
    account = user(plan="creator")
    expired = SimpleNamespace(
        id=uuid.uuid4(),
        platform="ios",
        product_id="creator_monthly",
        purchase_token="apple-original",
        status="active",
        expires_at=now - timedelta(days=2),
        auto_renewing=True,
        next_verification_at=now - timedelta(minutes=1),
    )
    # Refresh query sees the due row; reconciliation sees no unexpired source.
    db = SequencedDb([[expired], []])
    monkeypatch.setattr(entitlements, "_now", lambda: now)
    monkeypatch.setattr(
        store_billing,
        "verify",
        lambda *args, **kwargs: (_ for _ in ()).throw(store_billing.StoreError("down")),
    )
    original = settings.STORE_OUTAGE_GRACE_HOURS
    settings.STORE_OUTAGE_GRACE_HOURS = 24
    try:
        entitlements.refresh_store_entitlements(db, account)
    finally:
        settings.STORE_OUTAGE_GRACE_HOURS = original

    assert account.plan == "free"
    assert expired.next_verification_at == now + entitlements.STORE_RETRY_DELAY


def test_google_uses_latest_line_item_and_preserves_linked_token(monkeypatch):
    original = (settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON, settings.ANDROID_PACKAGE_NAME)
    settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON = "{}"
    settings.ANDROID_PACKAGE_NAME = "com.banterclips.app"
    monkeypatch.setattr(store_billing, "_google_access_token", lambda: "access")
    monkeypatch.setattr(
        store_billing.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "packageName": "com.banterclips.app",
                "subscriptionState": "SUBSCRIPTION_STATE_ACTIVE",
                "linkedPurchaseToken": "old-token",
                "externalAccountIdentifiers": {
                    "obfuscatedExternalAccountId": "banter-user-id"
                },
                "lineItems": [
                    {
                        "productId": "old_product",
                        "expiryTime": "2100-01-01T00:00:00Z",
                        "autoRenewingPlan": {"autoRenewEnabled": True},
                    },
                    {
                        "productId": "creator_monthly",
                        "expiryTime": "2099-01-01T00:00:00Z",
                        "autoRenewingPlan": {"autoRenewEnabled": True},
                    },
                ],
            },
        ),
    )
    try:
        result = store_billing.verify_google("new/token", "creator_monthly")
    finally:
        settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON, settings.ANDROID_PACKAGE_NAME = original

    assert result.product_id == "creator_monthly"
    assert result.purchase_token == "new/token"
    assert result.linked_purchase_token == "old-token"
    assert result.account_token == "banter-user-id"
    assert result.is_entitled


def _apple_jws(payload: dict) -> str:
    return jwt.encode(payload, key="", algorithm="none")


def test_apple_selects_latest_transaction_and_parses_auto_renew_zero(monkeypatch):
    original = (
        settings.APPLE_KEY_ID,
        settings.APPLE_ISSUER_ID,
        settings.APPLE_PRIVATE_KEY,
        settings.APPLE_BUNDLE_ID,
    )
    settings.APPLE_KEY_ID = "key"
    settings.APPLE_ISSUER_ID = "issuer"
    settings.APPLE_PRIVATE_KEY = "private"
    settings.APPLE_BUNDLE_ID = "com.banterclips.app"
    monkeypatch.setattr(store_billing, "_apple_jwt", lambda: "bearer")
    monkeypatch.setattr(
        store_billing.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "data": [
                    {
                        "lastTransactions": [
                            {
                                "status": 1,
                                "signedTransactionInfo": _apple_jws(
                                    {
                                        "bundleId": "com.banterclips.app",
                                        "productId": "creator_monthly",
                                        "originalTransactionId": "original-old",
                                        "appAccountToken": "banter-user-old",
                                        "expiresDate": 1767225600000,
                                    }
                                ),
                                "signedRenewalInfo": _apple_jws({"autoRenewStatus": "1"}),
                            },
                            {
                                "status": "1",
                                "signedTransactionInfo": _apple_jws(
                                    {
                                        "bundleId": "com.banterclips.app",
                                        "productId": "creator_monthly",
                                        "originalTransactionId": "original-new",
                                        "appAccountToken": "banter-user-new",
                                        "expiresDate": 4070908800000,
                                    }
                                ),
                                "signedRenewalInfo": _apple_jws({"autoRenewStatus": "0"}),
                            },
                            {
                                "status": 1,
                                "signedTransactionInfo": _apple_jws(
                                    {
                                        "bundleId": "com.banterclips.app",
                                        "productId": "another_product",
                                        "originalTransactionId": "unrelated",
                                        "appAccountToken": "another-user",
                                        "expiresDate": 4102444800000,
                                    }
                                ),
                                "signedRenewalInfo": _apple_jws({"autoRenewStatus": "1"}),
                            },
                        ]
                    }
                ]
            },
        ),
    )
    try:
        result = store_billing.verify_apple("transaction", "creator_monthly")
    finally:
        (
            settings.APPLE_KEY_ID,
            settings.APPLE_ISSUER_ID,
            settings.APPLE_PRIVATE_KEY,
            settings.APPLE_BUNDLE_ID,
        ) = original

    assert result.purchase_token == "original-new"
    assert result.status == "cancelled"
    assert result.account_token == "banter-user-new"
    assert result.auto_renewing is False
    assert result.is_entitled


def test_payment_sheet_passes_stable_idempotency_key(monkeypatch):
    original = (
        settings.STRIPE_SECRET_KEY,
        settings.STRIPE_PUBLISHABLE_KEY,
        settings.STRIPE_PRICE_CREATOR,
    )
    settings.STRIPE_SECRET_KEY = "sk_test_example"
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_example"
    settings.STRIPE_PRICE_CREATOR = "price_creator"

    calls = []

    class Subscription:
        @staticmethod
        def list(**kwargs):
            return {"data": []}

        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return {
                "id": "sub_pending",
                "latest_invoice": {"confirmation_secret": {"client_secret": "pi_secret"}},
            }

        @staticmethod
        def retrieve(_subscription_id, **kwargs):
            return {
                "id": "sub_pending",
                "status": "incomplete",
                "metadata": {
                    "client": "mobile",
                    "banterclips_user_id": str(account.id),
                },
                "latest_invoice": {"confirmation_secret": {"client_secret": "pi_secret"}},
            }

        @staticmethod
        def cancel(_subscription_id):
            return None

    class EphemeralKey:
        @staticmethod
        def create(**kwargs):
            return {"secret": "eph_secret"}

    fake_stripe = SimpleNamespace(Subscription=Subscription, EphemeralKey=EphemeralKey)
    account = user(plan="free")
    monkeypatch.setattr(billing, "_stripe", lambda: fake_stripe)
    monkeypatch.setattr(billing, "sync_subscription_state", lambda db, current: None)
    monkeypatch.setattr(billing, "_lock_billing_user", lambda db, current: current)
    monkeypatch.setattr(billing, "_ensure_customer", lambda db, current: "cus_123")
    monkeypatch.setattr(billing, "record_event", lambda *args, **kwargs: None)
    db = FakeDb()
    try:
        response = billing.mobile_payment_sheet(
            billing.MobilePaymentSheetBody(request_id="attempt-123"), account, db
        )
        retried = billing.mobile_payment_sheet(
            billing.MobilePaymentSheetBody(request_id="different-retry-id"), account, db
        )
    finally:
        (
            settings.STRIPE_SECRET_KEY,
            settings.STRIPE_PUBLISHABLE_KEY,
            settings.STRIPE_PRICE_CREATOR,
        ) = original

    assert response["subscription_id"] == "sub_pending"
    assert retried["subscription_id"] == "sub_pending"
    assert retried["reused"] is True
    assert len(calls) == 1
    assert calls[0]["idempotency_key"] == f"banter-mobile-sub:{account.id}:attempt-123"
