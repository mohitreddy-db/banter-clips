"""OpenRouter account balance for the admin dashboard.

The August incident: the OpenRouter balance went negative and the first
symptom was every generation failing. The dashboard's PROVIDER BALANCE card
and alert strip exist so that never happens silently again.

OpenRouter's `GET /api/v1/credits` returns lifetime purchases and usage;
balance = total_credits - total_usage (USD). The call is cheap but external,
so the result is cached in-process for 60 seconds — the same freshness the
dashboard promises for everything else.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx

from ..config import settings

log = logging.getLogger("banter.provider_balance")

CACHE_SECONDS = 60.0
_lock = threading.Lock()
_cached: dict | None = None
_cached_at = 0.0


def _fetch() -> dict | None:
    key = getattr(settings, "OPENROUTER_API_KEY", "") or ""
    if not key:
        return None
    resp = httpx.get(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    total = float(data.get("total_credits") or 0)
    used = float(data.get("total_usage") or 0)
    return {"balance_usd": round(total - used, 2), "total_credits": total, "total_usage": used}


def get() -> dict | None:
    """Cached balance info, or None when unavailable (no key / API error)."""
    global _cached, _cached_at
    with _lock:
        if _cached is not None and time.time() - _cached_at < CACHE_SECONDS:
            return _cached
    try:
        fresh = _fetch()
    except Exception:  # noqa: BLE001 — a billing-API hiccup must not 500 the dashboard
        log.exception("OpenRouter credits lookup failed")
        return _cached  # stale is better than nothing for an alert card
    with _lock:
        _cached = fresh
        _cached_at = time.time()
    return fresh
