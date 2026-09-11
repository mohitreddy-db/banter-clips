"""Additive schema migrations, applied on startup.

`Base.metadata.create_all` creates missing *tables* but never alters existing
ones, so a column added to `models.py` silently fails to appear on a database
that already exists — including production. This closes that gap for the one
change that matters in practice: adding a column.

Every statement here must be idempotent and additive. No drops, no renames, no
type changes, no data migrations: those need a real migration tool and a
maintenance window, and doing them from an app-startup hook is how you lose
data. When something here stops being expressible as `ADD COLUMN IF NOT
EXISTS`, that is the signal to adopt Alembic.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from .db import engine

log = logging.getLogger("banter.migrate")

# (table, column, type + default). Order does not matter; all are optional.
ADDITIONS: tuple[tuple[str, str, str], ...] = (
    ("clips", "current_step", "text"),
    ("clips", "video_key", "text"),
    ("clips", "poster_key", "text"),
    ("clips", "cost_usd", "numeric(7,3)"),
    ("clips", "provenance", "jsonb"),
    ("clips", "is_simulated", "boolean NOT NULL DEFAULT false"),
    ("clips", "resolution", "text NOT NULL DEFAULT '720p'"),
    ("users", "is_blocked", "boolean NOT NULL DEFAULT false"),
    ("clips", "script", "jsonb"),
    ("clips", "script_approved", "boolean NOT NULL DEFAULT false"),
    ("clips", "script_history", "jsonb"),
    ("users", "credits", "integer NOT NULL DEFAULT 0"),
    ("clips", "credits_charged", "integer NOT NULL DEFAULT 0"),
    ("clips", "sports", "text[] NOT NULL DEFAULT '{}'"),
    ("clips", "subjects", "text[] NOT NULL DEFAULT '{}'"),
    ("clips", "credits_quoted", "integer NOT NULL DEFAULT 0"),
    ("social_accounts", "refresh_token", "text"),
    ("clips", "direction", "text NOT NULL DEFAULT ''"),
    ("clips", "reference_key", "text"),
    ("clips", "edit_pending", "jsonb"),
    ("clips", "credits_edits", "integer NOT NULL DEFAULT 0"),
    ("publishes", "options", "jsonb"),
    # Provider-specific Stripe state. users.plan remains the combined cache
    # across Stripe plus Apple/Google store subscriptions.
    ("users", "stripe_subscription_status", "text"),
    ("users", "stripe_current_period_end", "timestamptz"),
    ("users", "stripe_cancel_at_period_end", "boolean NOT NULL DEFAULT false"),
    ("users", "stripe_mobile_pending_subscription_id", "text"),
)

# Idempotent statements beyond ADD COLUMN. The production schema (applied
# via schema.sql) carries a clips_status_check that predates "script_ready";
# rebuilding it from CLIP_STATUSES keeps the constraint in lockstep with the
# model — a status added in code but not here silently fails every write.
def _statements() -> tuple[str, ...]:
    from .models import CLIP_STATUSES, CREDIT_KINDS, SPORTS, TONES

    # Every enum-ish CHECK is rebuilt from the model tuple on boot. The status
    # constraint taught us why: it was written once in schema.sql, the model
    # gained "script_ready", and production rejected every write while local
    # (which had no constraint) passed its tests. Sport and tone carry the
    # same trap — the sport list grew from 4 to 12 and tones gained "Roast".
    return (
        # Explicit fallback for deployments where schema provisioning is run
        # separately from SQLAlchemy's create_all.
        "CREATE TABLE IF NOT EXISTS store_subscriptions ("
        "id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
        "user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
        "platform text NOT NULL CHECK (platform IN ('ios','android')), "
        "product_id text NOT NULL, purchase_token text NOT NULL, "
        "status text NOT NULL DEFAULT 'active' "
        "CHECK (status IN ('active','cancelled','expired')), "
        "expires_at timestamptz, auto_renewing boolean NOT NULL DEFAULT true, "
        "created_at timestamptz NOT NULL DEFAULT now(), "
        "last_verified_at timestamptz NOT NULL DEFAULT now(), "
        "next_verification_at timestamptz NOT NULL DEFAULT now(), "
        "CONSTRAINT store_sub_provider_token UNIQUE (platform, purchase_token))",
        # The draft branch may have created this table before next_verification_at
        # existed. CREATE TABLE IF NOT EXISTS cannot repair a partial table.
        "ALTER TABLE store_subscriptions ADD COLUMN IF NOT EXISTS "
        "next_verification_at timestamptz DEFAULT now()",
        "UPDATE store_subscriptions SET next_verification_at = now() "
        "WHERE next_verification_at IS NULL",
        "ALTER TABLE store_subscriptions ALTER COLUMN next_verification_at SET NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS store_sub_provider_token "
        "ON store_subscriptions (platform, purchase_token)",
        "CREATE INDEX IF NOT EXISTS store_subscriptions_user "
        "ON store_subscriptions (user_id, expires_at)",
        # Existing main rows only carry subscription_id. That id was written by
        # a successful Stripe sync, so preserve it as active until the next
        # webhook/API sync supplies the current status.
        "UPDATE users SET stripe_subscription_status = 'active' "
        "WHERE stripe_subscription_id IS NOT NULL "
        "AND stripe_subscription_status IS NULL",
        # "creating_voice" left the vocabulary (2026-08-31). Any row still
        # carrying it is a job that died mid-stage long ago; without this
        # UPDATE the rebuilt status constraint below would fail validation
        # and the whole migration transaction would roll back.
        "UPDATE clips SET status = 'failed', "
        "error = COALESCE(error, 'interrupted by a deploy') "
        "WHERE status = 'creating_voice'",
        # Creator prompts run to 500 characters; the plan gate is in the API.
        "ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_take_len",
        "ALTER TABLE clips ADD CONSTRAINT clips_take_len "
        "CHECK (char_length(take) BETWEEN 10 AND 500)",
        "ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_status_check",
        f"ALTER TABLE clips ADD CONSTRAINT clips_status_check "
        f"CHECK (status IN {CLIP_STATUSES!r})",
        "ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_sport_check",
        f"ALTER TABLE clips ADD CONSTRAINT clips_sport_check "
        f"CHECK (sport IN {SPORTS!r})",
        # The ledger's kinds grow too (edit_charge, 2026-09-02): a kind the
        # constraint predates makes every such charge silently fail on prod.
        "ALTER TABLE credit_entries DROP CONSTRAINT IF EXISTS credit_entries_kind_check",
        f"ALTER TABLE credit_entries ADD CONSTRAINT credit_entries_kind_check "
        f"CHECK (kind IN {CREDIT_KINDS!r})",
        "ALTER TABLE clips DROP CONSTRAINT IF EXISTS clips_tone_check",
        f"ALTER TABLE clips ADD CONSTRAINT clips_tone_check "
        f"CHECK (tone IN {TONES!r})",
    )


def _verify_required_billing_schema() -> None:
    """Fail deployment before traffic if mapped billing columns are absent."""
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT stripe_subscription_status, stripe_current_period_end, "
                    "stripe_cancel_at_period_end, stripe_mobile_pending_subscription_id "
                    "FROM users LIMIT 0"
                )
            )
            conn.execute(
                text(
                    "SELECT id, user_id, platform, product_id, purchase_token, status, "
                    "expires_at, auto_renewing, created_at, last_verified_at, "
                    "next_verification_at FROM store_subscriptions LIMIT 0"
                )
            )
            token_unique = conn.scalar(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM ("
                    "SELECT array_agg(a.attname ORDER BY key_col.ordinality) AS columns "
                    "FROM pg_index i "
                    "JOIN pg_class t ON t.oid = i.indrelid "
                    "JOIN pg_namespace n ON n.oid = t.relnamespace "
                    "JOIN LATERAL unnest(i.indkey::smallint[]) WITH ORDINALITY "
                    "AS key_col(attnum, ordinality) ON key_col.attnum > 0 "
                    "JOIN pg_attribute a ON a.attrelid = t.oid "
                    "AND a.attnum = key_col.attnum "
                    "WHERE n.nspname = current_schema() "
                    "AND t.relname = 'store_subscriptions' AND i.indisunique "
                    "GROUP BY i.indexrelid) unique_indexes "
                    "WHERE columns = ARRAY['purchase_token']::name[] "
                    "OR columns = ARRAY['platform','purchase_token']::name[])"
                )
            )
            if not token_unique:
                raise RuntimeError("store purchase tokens are not uniquely constrained")
    except Exception as exc:  # a half-migrated User mapping breaks every auth request
        raise RuntimeError(
            "required mobile billing schema is missing; apply "
            "backend/migrations/20260909_mobile_billing.sql before deployment"
        ) from exc


def apply() -> None:
    """Bring an existing database up to the current model.

    Historical additive migrations remain best-effort, but the billing fields
    mapped on every User query are verified afterwards. A missing required
    field fails startup instead of producing 500s on every authenticated route.
    """
    try:
        with engine.begin() as conn:
            for table, column, ddl in ADDITIONS:
                conn.execute(
                    text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {ddl}')
                )
            for statement in _statements():
                conn.execute(text(statement))
    except Exception:  # noqa: BLE001 — verification below decides if boot is safe
        log.exception("one or more additive migrations failed")
    _verify_required_billing_schema()
