"""Spend ceiling across all jobs.

`MAX_JOB_COST_USD` stops one runaway clip. It does nothing about the case that
actually empties an account: an ordinary day of ordinary users. At roughly
$2.40 a clip, two people using their free allowance costs more than $20.

So before a real generation starts, sum what the last 24 hours actually cost
— from `clips.cost_usd`, which the pipeline records per clip — and refuse if
the ceiling is reached. Refusing up front is much kinder than letting a run
start and die halfway: a clip that fails costs the user nothing (failures do
not count against the allowance) but costs us whatever was spent before the
provider said no.

Simulated runs are free and never counted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Clip

log = logging.getLogger("banter.spend")

WINDOW = timedelta(hours=24)


def spent_last_day(db: Session) -> float:
    """What generation has cost in the trailing 24 hours."""
    since = datetime.now(timezone.utc) - WINDOW
    total = db.scalar(
        select(func.coalesce(func.sum(Clip.cost_usd), 0)).where(Clip.created_at >= since)
    )
    return float(total or 0.0)


def ceiling() -> float:
    return float(getattr(settings, "MAX_DAILY_SPEND_USD", 0) or 0)


def allowed(db: Session) -> tuple[bool, float, float]:
    """(may we spend, spent so far, ceiling). Never raises.

    A database problem returns True: refusing every generation because a
    counting query failed would be a worse outcome than briefly overspending.
    """
    limit = ceiling()
    if limit <= 0:
        return True, 0.0, 0.0
    try:
        spent = spent_last_day(db)
    except Exception:  # noqa: BLE001
        log.exception("could not total recent spend; allowing the job")
        return True, 0.0, limit
    return spent < limit, spent, limit


OVER_BUDGET_MESSAGE = (
    "We've hit today's generation limit. Your allowance was not used — "
    "try again in a few hours."
)
