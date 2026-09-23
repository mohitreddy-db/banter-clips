# Mobile billing setup

The backend supports three independent subscription sources and derives one
Creator entitlement for the signed-in BanterClips account:

- Web: Stripe Checkout and Stripe webhooks.
- iOS: StoreKit purchase verified with App Store Server API.
- Android: Play Billing purchase verified with Google Play Developer API.

Creator is active while **any** verified source is active. A Stripe cancellation
cannot remove access paid for through Apple or Google, and an expired mobile
purchase cannot remove an active Stripe entitlement.

## API contract

All routes except the Stripe webhook require the normal BanterClips bearer token.

### Verify an iOS purchase

```http
POST /billing/mobile/verify
Authorization: Bearer <session-token>
Content-Type: application/json

{
  "platform": "ios",
  "product_id": "creator_monthly",
  "transaction_id": "<StoreKit transaction id>"
}
```

When creating the StoreKit purchase, set `appAccountToken` to the signed-in
BanterClips `user.id` UUID. The backend rejects a transaction whose signed
account token does not match the authenticated account. Call verification after
purchase and from **Restore Purchases**. The backend persists Apple's stable
`originalTransactionId`, not a client claim.

### Verify an Android purchase

```http
POST /billing/mobile/verify
Authorization: Bearer <session-token>
Content-Type: application/json

{
  "platform": "android",
  "product_id": "creator_monthly",
  "purchase_token": "<Play Billing purchase token>"
}
```

Before launching Play Billing, call `setObfuscatedAccountId(user.id)` on the
BillingFlowParams account identifiers. The backend compares Google's returned
`obfuscatedExternalAccountId` with the authenticated user and rejects a
mismatch. Call verification after purchase and whenever Play Billing returns an
owned purchase. After a successful backend verification, the app must
acknowledge the purchase through Play Billing within Google's deadline. Google
replacement-token lineage is also checked so a plan change cannot move a
subscription to another BanterClips account.

### Read combined state

```http
GET /billing/status
Authorization: Bearer <session-token>
```

The response includes the combined plan and active providers. Clients should
check this before showing a purchase button. If Creator is already active,
show where it is billed instead of encouraging a second subscription.

`GET /me/usage` remains the capability response used by existing clients.
Store expiry/reverification also runs before every authenticated capability
check, throttled by `STORE_REVERIFY_HOURS`. A temporary provider outage at
renewal preserves access only for `STORE_OUTAGE_GRACE_HOURS`; verification keeps
retrying every five minutes and fails closed after that bounded window.

### Optional native Stripe PaymentSheet

`POST /billing/mobile/payment-sheet` and `POST /billing/mobile/confirm` support
native Stripe distributions. The first request requires a stable client-created
`request_id` for retry idempotency:

```json
{"request_id":"a-uuid-created-once-per-checkout-attempt"}
```

Do **not** use Stripe PaymentSheet to sell digital Creator access in App Store
or Google Play builds unless the applicable store policy explicitly permits it.
Those builds should use their store SDK and `/billing/mobile/verify`.

## Backend environment

Copy the names from `.env.example`; secrets belong only in the backend runtime.

### Apple

1. Create the `creator_monthly` auto-renewable subscription in App Store Connect.
2. Create an App Store Server API / In-App Purchase private key.
3. Set:
   - `APPLE_KEY_ID`
   - `APPLE_ISSUER_ID`
   - `APPLE_PRIVATE_KEY` (the `.p8` content; escaped `\\n` is accepted)
   - `APPLE_BUNDLE_ID`
4. Set `STORE_PRODUCT_CREATOR=creator_monthly`.
5. Test through StoreKit sandbox/TestFlight. The backend automatically tries
   Apple's production endpoint first and sandbox second.

### Google Play

1. Create and activate the `creator_monthly` subscription and base plan.
2. Enable Google Play Android Developer API for the linked Google Cloud project.
3. Create a service account and grant it subscription/order read access in Play
   Console API access.
4. Set:
   - `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` to the complete JSON key
   - `ANDROID_PACKAGE_NAME`
   - `STORE_PRODUCT_CREATOR=creator_monthly`
5. Test with a Play license tester on a Play-delivered build.

### Stripe PaymentSheet (optional)

Set `STRIPE_PUBLISHABLE_KEY` in addition to the existing Stripe secret, price,
and webhook values. Set `STRIPE_MOBILE_API_VERSION` to the API version required
by the installed native Stripe SDK.

## Deployment

1. Before restarting application code, apply
   `migrations/20260909_mobile_billing.sql` through the Supabase SQL editor (or
   with a privileged Postgres migration connection). It is additive and safe to
   rerun. Startup verifies these required fields and intentionally refuses to
   serve if the migration is missing, rather than breaking every authenticated
   request later.
2. Install updated Python requirements (`PyJWT[crypto]` is required).
3. Add the store environment values and deploy/restart the API.
4. `schema.sql` contains the same definitions for fresh databases; startup
   `create_all` and `db_migrate` remain idempotent fallbacks.
5. Check `/health/ready`, confirm `GET /billing/status`, then test existing web
   top-ups and one sandbox purchase from each mobile store.

## Notification follow-up

This change enforces stored expiry and periodically asks each store for current
state while the account is active. Verified Apple App Store Server Notifications
V2 and Google Real-time Developer Notifications are not exposed yet. Add them
before high-volume launch for near-real-time cancellation/refund updates; keep
the periodic recheck as a fallback because notifications can be delayed.
