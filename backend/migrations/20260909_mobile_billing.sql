-- Mobile billing rollout for an existing BanterClips Postgres/Supabase database.
-- Additive and safe to rerun before deploying the matching backend code.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_status text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_current_period_end timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_cancel_at_period_end
    boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_mobile_pending_subscription_id text;

-- Existing subscription ids were written only after a live Stripe sync in main.
-- Preserve those users during rollout; future webhooks/API syncs refresh status.
UPDATE users
SET stripe_subscription_status = 'active'
WHERE stripe_subscription_id IS NOT NULL
  AND stripe_subscription_status IS NULL;

CREATE TABLE IF NOT EXISTS store_subscriptions (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform              text NOT NULL
                          CHECK (platform IN ('ios', 'android')),
    product_id            text NOT NULL,
    purchase_token        text NOT NULL,
    status                text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'cancelled', 'expired')),
    expires_at            timestamptz,
    auto_renewing         boolean NOT NULL DEFAULT true,
    created_at            timestamptz NOT NULL DEFAULT now(),
    last_verified_at      timestamptz NOT NULL DEFAULT now(),
    next_verification_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT store_sub_provider_token UNIQUE (platform, purchase_token)
);

-- Repair the earlier draft table if it was briefly deployed before this final
-- migration; CREATE TABLE IF NOT EXISTS alone does not add missing columns.
ALTER TABLE store_subscriptions ADD COLUMN IF NOT EXISTS next_verification_at
    timestamptz DEFAULT now();
UPDATE store_subscriptions
SET next_verification_at = now()
WHERE next_verification_at IS NULL;
ALTER TABLE store_subscriptions ALTER COLUMN next_verification_at SET NOT NULL;

-- The draft used globally unique purchase_token, which is stronger and remains
-- valid. This named provider-scoped index also protects any partial table.
CREATE UNIQUE INDEX IF NOT EXISTS store_sub_provider_token
    ON store_subscriptions (platform, purchase_token);

CREATE INDEX IF NOT EXISTS store_subscriptions_user
    ON store_subscriptions (user_id, expires_at);
