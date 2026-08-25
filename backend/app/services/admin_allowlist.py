"""Who is an admin — env bootstrap list + DB-managed additions.

`ADMIN_EMAILS` (env) remains the bootstrap: those addresses are always
admins and cannot be removed from the console, so an operator can never
lock themselves out by clicking the wrong button. The console-managed list
lives in runtime_settings under ``admin_emails`` (comma-separated) and is
unioned with the env set.

``is_admin_email`` sits on the request path (User.is_admin is checked on
every /me and admin call), so the DB list is cached in-process for 30s —
adding/removing an admin takes effect immediately on the worker that made
the change and within 30s on its siblings.
"""

from __future__ import annotations

import logging
import threading
import time

from ..config import settings

log = logging.getLogger("banter.admin_allowlist")

KEY = "admin_emails"
CACHE_SECONDS = 30.0

_lock = threading.Lock()
_cached: set[str] = set()
_cached_at = 0.0


def env_admins() -> set[str]:
    return {e.lower() for e in settings.admin_emails}


def _load_db_admins() -> set[str]:
    # Local imports: models imports this module lazily from a property, so
    # importing models at module load would be a cycle.
    from ..db import SessionLocal
    from ..models import RuntimeSetting

    db = SessionLocal()
    try:
        row = db.get(RuntimeSetting, KEY)
        if row is None or not row.value.strip():
            return set()
        return {e.strip().lower() for e in row.value.split(",") if e.strip()}
    finally:
        db.close()


def db_admins(fresh: bool = False) -> set[str]:
    global _cached, _cached_at
    with _lock:
        if not fresh and time.time() - _cached_at < CACHE_SECONDS:
            return set(_cached)
    try:
        loaded = _load_db_admins()
    except Exception:  # noqa: BLE001 — an allowlist read problem must not break auth
        log.exception("could not read DB admin list; using env admins only")
        return set(_cached)
    with _lock:
        _cached = loaded
        _cached_at = time.time()
    return set(loaded)


def invalidate() -> None:
    global _cached_at
    with _lock:
        _cached_at = 0.0


def is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    email = email.lower()
    return email in env_admins() or email in db_admins()


def save_db_admins(db, emails: set[str], updated_by: str) -> None:
    """Persist the console-managed list and refresh this process's cache."""
    from . import runtime_settings

    runtime_settings.set_value(db, KEY, ",".join(sorted(emails)), updated_by)
    invalidate()
