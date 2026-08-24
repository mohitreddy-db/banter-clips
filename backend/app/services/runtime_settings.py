"""Operator-editable runtime settings, DB-backed with env fallback.

The spend caps (`MAX_DAILY_SPEND_USD`, `MAX_JOB_COST_USD`) started life as
environment variables, which meant changing them required SSH and a restart —
the exact workflow the admin console exists to kill. Values written here win
over the env; a missing row falls back to the env default, so a fresh
database behaves exactly as before.

Also holds:
  - ``generation_paused`` — the kill switch. When truthy, spend.allowed()
    refuses every new real generation.
  - ``worker_heartbeat_at`` — ISO timestamp the worker refreshes every
    HEARTBEAT_SECONDS; the dashboard derives "worker down" from its age.

Reads happen on hot paths (once per generation start), so each helper is a
single primary-key SELECT — no caching layer to go stale.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import RuntimeSetting

log = logging.getLogger("banter.runtime_settings")

KEY_DAILY_CAP = "max_daily_spend_usd"
KEY_JOB_CAP = "max_job_cost_usd"
KEY_PAUSED = "generation_paused"
KEY_WORKER_HEARTBEAT = "worker_heartbeat_at"


def get_raw(db: Session, key: str) -> str | None:
    try:
        row = db.get(RuntimeSetting, key)
        return row.value if row is not None else None
    except Exception:  # noqa: BLE001 — settings must never take the app down
        log.exception("runtime setting read failed for %s", key)
        # A failed statement aborts the Postgres transaction; without this
        # rollback every later query on the same session fails too.
        db.rollback()
        return None


def set_value(db: Session, key: str, value: str, updated_by: str = "") -> None:
    row = db.get(RuntimeSetting, key)
    if row is None:
        row = RuntimeSetting(key=key, value=str(value), updated_by=updated_by)
        db.add(row)
    else:
        row.value = str(value)
        row.updated_by = updated_by
    db.flush()


def get_float(db: Session, key: str, env_default: float) -> float:
    raw = get_raw(db, key)
    if raw is None:
        return env_default
    try:
        return float(raw)
    except ValueError:
        log.warning("runtime setting %s=%r is not a number; using env default", key, raw)
        return env_default


def daily_cap(db: Session) -> float:
    return get_float(db, KEY_DAILY_CAP, float(getattr(settings, "MAX_DAILY_SPEND_USD", 0) or 0))


def job_cap(db: Session) -> float:
    return get_float(db, KEY_JOB_CAP, float(getattr(settings, "MAX_JOB_COST_USD", 0) or 0))


def generation_paused(db: Session) -> bool:
    return (get_raw(db, KEY_PAUSED) or "").lower() in ("1", "true", "yes", "on")


def beat_worker_heartbeat(db: Session, worker: str) -> None:
    set_value(db, KEY_WORKER_HEARTBEAT, datetime.now(timezone.utc).isoformat(), updated_by=worker)


def worker_heartbeat(db: Session) -> tuple[datetime | None, str]:
    """(last heartbeat time, worker name) — (None, "") if never beaten."""
    try:
        row = db.get(RuntimeSetting, KEY_WORKER_HEARTBEAT)
    except Exception:  # noqa: BLE001
        db.rollback()
        return None, ""
    if row is None:
        return None, ""
    try:
        return datetime.fromisoformat(row.value), row.updated_by
    except ValueError:
        return None, row.updated_by
