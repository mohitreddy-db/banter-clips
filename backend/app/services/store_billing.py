"""Server-side verification of Apple and Google Creator subscriptions.

The mobile client never grants itself an entitlement. It sends a transaction
identifier (Apple) or purchase token (Google), and this module asks the store
for the current subscription state. Only the normalized ``Entitlement`` result
is allowed to update local billing state.

Server-to-server notifications are intentionally not accepted here yet. Until
verified Apple ASSN V2 and Google RTDN handlers are added, active accounts are
periodically rechecked by ``services.entitlements`` and always rechecked when
stored expiry is reached.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

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
    """The store could not be reached or returned an unusable response."""


@dataclass(frozen=True)
class Entitlement:
    """Normalized subscription state returned by Apple or Google."""

    purchase_token: str
    product_id: str
    expires_at: datetime | None
    auto_renewing: bool
    status: str
    # Apple appAccountToken or Google Play obfuscatedExternalAccountId. Mobile
    # purchase code must set this to the signed-in BanterClips user UUID.
    account_token: str | None = None
    linked_purchase_token: str | None = None

    @property
    def is_entitled(self) -> bool:
        return (
            self.status in ("active", "cancelled")
            and self.expires_at is not None
            and self.expires_at > datetime.now(timezone.utc)
        )


# --------------------------------------------------------------------- Google


def google_configured() -> bool:
    return bool(settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON and settings.ANDROID_PACKAGE_NAME)


def _google_access_token() -> str:
    """Mint an OAuth2 access token from the configured service-account key."""
    try:
        key = json.loads(settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON)
        client_email = key["client_email"]
        private_key = key["private_key"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise StoreError("Google Play service-account JSON is invalid") from exc

    now = int(time.time())
    try:
        assertion = pyjwt.encode(
            {
                "iss": client_email,
                "scope": "https://www.googleapis.com/auth/androidpublisher",
                "aud": GOOGLE_TOKEN_URL,
                "iat": now,
                "exp": now + 3600,
            },
            private_key,
            algorithm="RS256",
        )
    except Exception as exc:  # PyJWT/cryptography expose several key errors
        raise StoreError("Google Play service-account key could not sign a token") from exc

    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise StoreError("could not reach Google's token endpoint") from exc
    if response.status_code != 200:
        raise StoreError(f"Google refused the service account ({response.status_code})")
    try:
        access_token = response.json()["access_token"]
    except (ValueError, KeyError, TypeError) as exc:
        raise StoreError("Google's token response was malformed") from exc
    if not isinstance(access_token, str) or not access_token:
        raise StoreError("Google's token response contained no access token")
    return access_token


def verify_google(purchase_token: str, requested_product_id: str) -> Entitlement:
    """Verify a subscription with Google Play's subscriptionsv2 endpoint."""
    if not google_configured():
        raise StoreError("Google Play billing is not configured on this server")
    if not purchase_token:
        raise StoreError("a Google purchase must carry its purchase token")

    access_token = _google_access_token()
    url = (
        f"{GOOGLE_PLAY_API}/applications/{quote(settings.ANDROID_PACKAGE_NAME, safe='')}"
        f"/purchases/subscriptionsv2/tokens/{quote(purchase_token, safe='')}"
    )
    try:
        response = httpx.get(
            url, headers={"Authorization": f"Bearer {access_token}"}, timeout=TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise StoreError("could not reach the Play Developer API") from exc

    if response.status_code == 404:
        return Entitlement(purchase_token, requested_product_id, None, False, "expired")
    if response.status_code != 200:
        raise StoreError(f"Play Developer API returned {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise StoreError("Play Developer API returned malformed JSON") from exc
    if not isinstance(body, dict):
        raise StoreError("Play Developer API returned an unusable subscription")

    response_package = body.get("packageName")
    if response_package and response_package != settings.ANDROID_PACKAGE_NAME:
        raise StoreError("Google returned a subscription for another Android package")

    candidates: list[tuple[datetime, dict]] = []
    for item in body.get("lineItems") or []:
        if not isinstance(item, dict):
            continue
        expires_at = _parse_rfc3339(item.get("expiryTime"))
        if expires_at is not None:
            candidates.append((expires_at, item))
    if not candidates:
        raise StoreError("Play Developer API returned no usable subscription line item")

    # Plan changes can leave multiple line items. Prefer the requested Creator
    # product, then choose its latest expiry; list position is not a contract.
    matching = [
        candidate
        for candidate in candidates
        if candidate[1].get("productId") == requested_product_id
    ]
    expires_at, item = max(matching or candidates, key=lambda candidate: candidate[0])
    actual_product_id = item.get("productId")
    if not isinstance(actual_product_id, str) or not actual_product_id:
        raise StoreError("Google's subscription line item has no product id")

    state = str(body.get("subscriptionState") or "")
    auto_value = (item.get("autoRenewingPlan") or {}).get("autoRenewEnabled")
    auto_renewing = auto_value is True or str(auto_value).lower() == "true"
    if state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"):
        status = "active" if auto_renewing else "cancelled"
    elif state == "SUBSCRIPTION_STATE_CANCELED":
        status = "cancelled"
        auto_renewing = False
    else:
        # Pending, paused, on-hold and expired do not unlock Creator.
        status = "expired"
        auto_renewing = False

    external_ids = body.get("externalAccountIdentifiers") or {}
    account_token = None
    if isinstance(external_ids, dict):
        candidate = external_ids.get("obfuscatedExternalAccountId")
        if isinstance(candidate, str) and candidate:
            account_token = candidate

    linked_token = body.get("linkedPurchaseToken")
    if not isinstance(linked_token, str):
        linked_token = None
    return Entitlement(
        purchase_token=purchase_token,
        product_id=actual_product_id,
        expires_at=expires_at,
        auto_renewing=auto_renewing,
        status=status,
        account_token=account_token,
        linked_purchase_token=linked_token,
    )


# ---------------------------------------------------------------------- Apple


def apple_configured() -> bool:
    return bool(
        settings.APPLE_KEY_ID
        and settings.APPLE_ISSUER_ID
        and settings.APPLE_PRIVATE_KEY
        and settings.APPLE_BUNDLE_ID
    )


def _apple_jwt() -> str:
    """Create the ES256 bearer token required by App Store Server API."""
    now = int(time.time())
    try:
        return pyjwt.encode(
            {
                "iss": settings.APPLE_ISSUER_ID,
                "iat": now,
                "exp": now + 1800,
                "aud": "appstoreconnect-v1",
                "bid": settings.APPLE_BUNDLE_ID,
            },
            settings.APPLE_PRIVATE_KEY.replace("\\n", "\n"),
            algorithm="ES256",
            headers={"kid": settings.APPLE_KEY_ID, "typ": "JWT"},
        )
    except Exception as exc:  # invalid PEM/key shape varies by crypto backend
        raise StoreError("Apple private key could not sign an API token") from exc


def verify_apple(transaction_id: str, requested_product_id: str) -> Entitlement:
    """Verify a transaction with the App Store Server API.

    Production is checked first and sandbox second because TestFlight and App
    Review purchases use the sandbox even when the app binary is production.
    """
    if not apple_configured():
        raise StoreError("Apple billing is not configured on this server")
    if not transaction_id:
        raise StoreError("an iOS purchase must carry its transaction id")

    headers = {"Authorization": f"Bearer {_apple_jwt()}"}
    body: dict | None = None
    for base_url in (APPLE_PRODUCTION, APPLE_SANDBOX):
        try:
            response = httpx.get(
                f"{base_url}/subscriptions/{quote(transaction_id, safe='')}",
                headers=headers,
                timeout=TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise StoreError("could not reach the App Store Server API") from exc
        if response.status_code == 200:
            try:
                decoded = response.json()
            except ValueError as exc:
                raise StoreError("App Store Server API returned malformed JSON") from exc
            if not isinstance(decoded, dict):
                raise StoreError("App Store Server API returned an unusable subscription")
            body = decoded
            break
        if response.status_code == 404:
            continue
        raise StoreError(f"App Store Server API returned {response.status_code}")

    if body is None:
        return Entitlement(transaction_id, requested_product_id, None, False, "expired")

    candidates: list[tuple[datetime, int, dict, dict]] = []
    saw_transaction = False
    for group in body.get("data") or []:
        if not isinstance(group, dict):
            continue
        for transaction in group.get("lastTransactions") or []:
            if not isinstance(transaction, dict):
                continue
            saw_transaction = True
            info = _decode_apple_jws(transaction.get("signedTransactionInfo"))
            renewal = _decode_apple_jws(transaction.get("signedRenewalInfo"))
            if info.get("bundleId") != settings.APPLE_BUNDLE_ID:
                continue
            expires_at = _parse_apple_milliseconds(info.get("expiresDate"))
            product_id = info.get("productId")
            if expires_at is None or not isinstance(product_id, str) or not product_id:
                continue
            try:
                apple_status = int(transaction.get("status"))
            except (TypeError, ValueError):
                continue
            candidates.append((expires_at, apple_status, info, renewal))

    if not candidates:
        if saw_transaction:
            raise StoreError("Apple returned no valid subscription transaction")
        return Entitlement(transaction_id, requested_product_id, None, False, "expired")

    # Apple may return more than one subscription-group entry. Prefer the
    # requested Creator product and choose by expiry rather than response order.
    matching = [
        candidate
        for candidate in candidates
        if candidate[2].get("productId") == requested_product_id
    ]
    expires_at, apple_status, info, renewal = max(
        matching or candidates, key=lambda value: value[0]
    )
    auto_renewing = str(renewal.get("autoRenewStatus")) == "1"
    if apple_status in (1, 3, 4):
        status = "active" if auto_renewing else "cancelled"
    else:  # 2 expired, 5 revoked, and unknown future states
        status = "expired"
        auto_renewing = False

    original_id = info.get("originalTransactionId") or transaction_id
    product_id = info.get("productId") or requested_product_id
    return Entitlement(
        purchase_token=str(original_id),
        product_id=str(product_id),
        expires_at=expires_at,
        auto_renewing=auto_renewing,
        status=status,
        account_token=(
            str(info["appAccountToken"])
            if info.get("appAccountToken") is not None
            else None
        ),
    )


def _decode_apple_jws(token: str | None) -> dict:
    """Decode JWS returned directly by Apple's authenticated HTTPS API.

    This helper must not be reused for public App Store notifications: those
    require full signature and certificate-chain verification before decoding.
    """
    if not token:
        return {}
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
    except pyjwt.PyJWTError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_apple_milliseconds(value: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _parse_rfc3339(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ------------------------------------------------------------------ dispatch


def verify(
    platform: str,
    *,
    purchase_token: str,
    product_id: str,
    transaction_id: str | None,
) -> Entitlement:
    if platform == "android":
        return verify_google(purchase_token, product_id)
    if platform == "ios":
        return verify_apple(transaction_id or "", product_id)
    raise StoreError(f"unknown platform {platform!r}")


def configured(platform: str) -> bool:
    if platform == "android":
        return google_configured()
    if platform == "ios":
        return apple_configured()
    return False
