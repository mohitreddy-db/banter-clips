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
    except Exception:  # noqa: BLE001 — boot must survive a migration problem
        log.exception("additive migrations failed; continuing with the existing schema")
