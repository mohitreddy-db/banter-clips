"""Receipt verification for Apple and Google store subscriptions (BR-15).

Design principles, deliberately the same ones `routers/billing.py` states for
Stripe:

- **The store is the ledger.** We never mirror transactions; we store the
  derived entitlement (`store_subscriptions` + `users.plan`) and re-derive it
  from the store whenever we are asked to.
- **The client is never trusted.** A phone saying "the purchase succeeded" is
  a request to go and check, nothing more. Only the functions here — after a
  round trip to Apple or Google — may return an entitlement.
- **Idempotent.** Verification is keyed on the store's own purchase token, so
  a retry after a dropped connection converges instead of double-granting.
- **Self-healing expiry.** Every result carries the store's `expires_at`, so a
  subscription that lapses downgrades on the next check even if we never
  receive a server-to-server notification about it.

Without credentials configured both verifiers report "not configured" and the
endpoint answers 503 — the same shape as the Stripe path, so a dev machine
runs the whole app with no store setup at all.

What is deliberately NOT here yet: server-to-server notifications (Google
RTDN via Pub/Sub, Apple App Store Server Notifications V2). Those make a
cancellation or a billing failure visible within minutes instead of at the
next check. The expiry above is the safety net until they land; see
mobile/README.md.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import jwt as pyjwt

from ..config import settings

log = logging.getLogger("banter.store_billing")

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_PLAY_API = "https://androidpublisher.googleapis.com/androidpublisher/v3"
APPLE_PRODUCTION = "https://api.storekit.itunes.apple.com/inApps/v1"
APPLE_SANDBOX = "https://api.storekit-sandbox.itunes.apple.com/inApps/v1"

TIMEOUT = 15


class StoreError(Exception):
    """The store could not be asked, or answered something unusable.

    Deliberately distinct from "the store said this receipt is not valid":
    the first is our problem and should be retried, the second is an answer
    and must not grant anything.
    """


@dataclass(frozen=True)
class Entitlement:
    """What a store said about one subscription. The only thing allowed to
    flip a user onto Creator."""

    #: The store's stable identifier for this subscription. Unique per
    #: subscriber, which is what makes replay across accounts impossible.
    purchase_token: str
    product_id: str
    expires_at: datetime | None
    auto_renewing: bool
    #: "active" | "expired" | "cancelled". Cancelled is still entitled until
    #: expires_at — the same rule as cancel_at_period_end on Stripe.
    status: str

    @property
    def is_entitled(self) -> bool:
        if self.status == "expired":
            return False
        if self.expires_at is None:
            # No expiry from the store is not a licence for forever. Treat it
            # as unusable rather than granting an unbounded plan.
            return False
        return self.expires_at > datetime.now(timezone.utc)


# --------------------------------------------------------------------- google


def google_configured() -> bool:
    return bool(settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON and settings.ANDROID_PACKAGE_NAME)


def _google_access_token() -> str:
    """Mint an OAuth2 access token from the service-account key.

    Done by hand rather than with google-auth: it is one signed JWT and one
    POST, and it saves pulling a large dependency tree onto the droplet for
    exactly this.
    """
    try:
        key = json.loads(settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as exc:
        raise StoreError("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is not valid JSON") from exc

    now = int(time.time())
    assertion = pyjwt.encode(
        {
            "iss": key["client_email"],
            "scope": "https://www.googleapis.com/auth/androidpublisher",
            "aud": GOOGLE_TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        },
        key["private_key"],
        algorithm="RS256",
    )
    try:
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise StoreError("could not reach Google's token endpoint") from exc
    if resp.status_code != 200:
        raise StoreError(f"Google refused the service account ({resp.status_code})")
    return resp.json()["access_token"]


def verify_google(purchase_token: str, product_id: str) -> Entitlement:
    """Ask the Play Developer API about one subscription purchase.

    Uses subscriptionsv2, which reports the *subscription* rather than a
    single purchase — so an upgrade, a resubscribe, or a plan change all come
    back as the same object with a current expiry.
    """
    if not google_configured():
        raise StoreError("Google Play billing is not configured on this server")

    token = _google_access_token()
    url = (
        f"{GOOGLE_PLAY_API}/applications/{settings.ANDROID_PACKAGE_NAME}"
        f"/purchases/subscriptionsv2/tokens/{purchase_token}"
    )
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise StoreError("could not reach the Play Developer API") from exc

    if resp.status_code == 404:
        # Google does not know this token. That is an answer, not an outage.
        return Entitlement(purchase_token, product_id, None, False, "expired")
    if resp.status_code != 200:
        raise StoreError(f"Play Developer API returned {resp.status_code}")

    body = resp.json()
    # subscriptionState: SUBSCRIPTION_STATE_ACTIVE / _CANCELED / _EXPIRED /
    # _IN_GRACE_PERIOD / _ON_HOLD / _PAUSED / _PENDING.
    state = body.get("subscriptionState", "")
    line_items = body.get("lineItems") or []
    first = line_items[0] if line_items else {}
    expires_at = _parse_rfc3339(first.get("expiryTime"))
    auto_renewing = bool((first.get("autoRenewingPlan") or {}).get("autoRenewEnabled"))

    if state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"):
        # Grace period counts as entitled on purpose: Google is still retrying
        # the payment, and cutting someone off mid-retry is a support ticket.
        status = "active"
    elif state == "SUBSCRIPTION_STATE_CANCELED":
        status = "cancelled"  # still entitled until expiry
    else:
        status = "expired"

    return Entitlement(
        purchase_token=purchase_token,
        product_id=first.get("productId") or product_id,
        expires_at=expires_at,
        auto_renewing=auto_renewing,
        status=status,
    )


# ---------------------------------------------------------------------- apple


def apple_configured() -> bool:
    return bool(
        settings.APPLE_KEY_ID
        and settings.APPLE_ISSUER_ID
        and settings.APPLE_PRIVATE_KEY
        and settings.APPLE_BUNDLE_ID
    )


def _apple_jwt() -> str:
    """The ES256 bearer token the App Store Server API expects."""
    now = int(time.time())
    return pyjwt.encode(
        {
            "iss": settings.APPLE_ISSUER_ID,
            "iat": now,
            "exp": now + 1800,  # Apple rejects anything over an hour
            "aud": "appstoreconnect-v1",
            "bid": settings.APPLE_BUNDLE_ID,
        },
        settings.APPLE_PRIVATE_KEY.replace("\\n", "\n"),
        algorithm="ES256",
        headers={"kid": settings.APPLE_KEY_ID, "typ": "JWT"},
    )


def verify_apple(transaction_id: str, product_id: str) -> Entitlement:
    """Ask the App Store Server API about one subscription.

    Production is tried first and sandbox second, because a build under review
    — and every TestFlight build — reports sandbox transactions that production
    answers 404 for. Getting this backwards is why "it works for me but App
    Review says it doesn't" happens.

    Note this uses the App Store Server API rather than the old
    `verifyReceipt` endpoint, which Apple has deprecated.
    """
    if not apple_configured():
        raise StoreError("Apple billing is not configured on this server")

    headers = {"Authorization": f"Bearer {_apple_jwt()}"}
    body = None
    for base in (APPLE_PRODUCTION, APPLE_SANDBOX):
        try:
            resp = httpx.get(
                f"{base}/subscriptions/{transaction_id}", headers=headers, timeout=TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise StoreError("could not reach the App Store Server API") from exc
        if resp.status_code == 200:
            body = resp.json()
            break
        if resp.status_code == 404:
            continue  # try sandbox
        raise StoreError(f"App Store Server API returned {resp.status_code}")

    if body is None:
        # Neither environment knows this transaction.
        return Entitlement(transaction_id, product_id, None, False, "expired")

    # data[] is per subscription group; lastTransactions[] holds the current
    # state, with the useful parts inside two signed JWS payloads.
    transactions = []
    for group in body.get("data") or []:
        transactions.extend(group.get("lastTransactions") or [])
    if not transactions:
        return Entitlement(transaction_id, product_id, None, False, "expired")

    current = transactions[0]
    # status: 1 active · 2 expired · 3 in billing retry · 4 in grace ·
    # 5 revoked.
    apple_status = current.get("status")
    info = _decode_jws(current.get("signedTransactionInfo"))
    renewal = _decode_jws(current.get("signedRenewalInfo"))

    expires_ms = info.get("expiresDate")
    expires_at = (
        datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc) if expires_ms else None
    )
    auto_renewing = bool(renewal.get("autoRenewStatus"))

    if apple_status in (1, 3, 4):
        # 1 active, 3 in billing retry, 4 in grace. All three are entitled
        # until the expiry date; cutting someone off while Apple is still
        # retrying their card is a support ticket, not a policy.
        # Auto-renew off means it is running out — the same state Stripe
        # calls cancel_at_period_end, and the UI words it the same way.
        status = "active" if auto_renewing else "cancelled"
    else:
        status = "expired"  # 2 expired, 5 revoked

    # The ORIGINAL transaction id is the stable per-subscriber key. The
    # per-renewal transaction id changes every month, so keying on it would
    # create a new row (and a new "purchase") every billing cycle.
    original_id = info.get("originalTransactionId") or transaction_id

    return Entitlement(
        purchase_token=str(original_id),
        product_id=info.get("productId") or product_id,
        expires_at=expires_at,
        auto_renewing=auto_renewing,
        status=status,
    )


def _decode_jws(token: str | None) -> dict:
    """Read the payload of one of Apple's signed JWS blobs.

    The signature is deliberately NOT checked here, and that is safe for one
    specific reason: this blob did not come from the client. It came from an
    authenticated HTTPS call to Apple's own API, so the transport already
    established who said it. Verifying the x5c chain would add a certificate
    store to maintain for no extra guarantee on this path.

    If a JWS ever arrives from somewhere else — an App Store Server
    Notification posted to a public webhook, for instance — it MUST be
    signature-verified before it is believed. Do not reuse this function there.
    """
    if not token:
        return {}
    try:
        return pyjwt.decode(token, options={"verify_signature": False})
    except pyjwt.PyJWTError:
        log.warning("could not decode an Apple JWS payload")
        return {}


def _parse_rfc3339(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ------------------------------------------------------------------ dispatch


def verify(platform: str, *, purchase_token: str, product_id: str, transaction_id: str | None) -> Entitlement:
    """Verify a receipt with whichever store it came from."""
    if platform == "android":
        return verify_google(purchase_token, product_id)
    if platform == "ios":
        # On iOS the useful key is the transaction id; the base64 receipt the
        # client also sends is only a fallback for older StoreKit payloads.
        if not transaction_id:
            raise StoreError("an iOS purchase must carry its transaction id")
        return verify_apple(transaction_id, product_id)
    raise StoreError(f"unknown platform {platform!r}")


def configured(platform: str) -> bool:
    return google_configured() if platform == "android" else apple_configured()
