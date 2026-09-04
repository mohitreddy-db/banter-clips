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


def apply() -> None:
    """Bring an existing database up to the current model. Never raises.

    A failure here must not stop the API booting: the columns are additive, so
    the worst case is a feature degrading rather than the service being down.
    """
    try:
        with engine.begin() as conn:
            for table, column, ddl in ADDITIONS:
                conn.execute(
                    text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {ddl}')
                )
            for statement in _statements():
                conn.execute(text(statement))
    except Exception:  # noqa: BLE001 — boot must survive a migration problem
        log.exception("additive migrations failed; continuing with the existing schema")
