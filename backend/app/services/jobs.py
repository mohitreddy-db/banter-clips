"""The work queue: enqueue, claim, finish, reclaim.

Backed by Postgres because it is already here and already backed up, and
because `SELECT ... FOR UPDATE SKIP LOCKED` is precisely the primitive a queue
needs: several workers can poll the same table and each takes a different row
without blocking the others.

Three properties matter more than throughput at this scale:

**Nothing is lost.** A job is a row. Deploying the API, restarting a worker or
losing the box leaves the row queued or reclaimable, so the work resumes.

**Nothing runs twice.** Claiming is a locked update inside one transaction, and
`enqueue` refuses to add a second live job for a clip that already has one — a
double-clicked button or a retried HTTP request cannot bill a render twice.

**Nothing gets stranded.** A worker refreshes `locked_at` while it works. If it
dies, the lock goes stale and another worker reclaims the job, up to
`max_attempts`, after which the clip is failed honestly.
"""

from __future__ import annotations

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Job

log = logging.getLogger("banter.jobs")

KIND_GENERATE = "generate_clip"

# A worker refreshes its lock this often; a lock older than STALE_AFTER is
# assumed dead. The gap is generous because a single scene can animate for
# two minutes with no natural checkpoint.
HEARTBEAT_SECONDS = 30
STALE_AFTER = timedelta(minutes=10)

# Retry once by default: generation failures are usually deterministic (a bad
# take, a provider outage), so a third attempt mostly burns money.
DEFAULT_MAX_ATTEMPTS = 2
RETRY_BACKOFF = timedelta(seconds=60)

LIVE_STATUSES = ("queued", "running")


def worker_name() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- producing

def enqueue(db: Session, clip_id: uuid.UUID, kind: str = KIND_GENERATE,
            max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> Job | None:
    """Queue work for a clip, unless it already has some. Never raises.

    Returns the existing job when one is live, so callers can treat enqueue as
    idempotent — which is what makes a retried POST safe.
    """
    try:
        existing = db.scalar(
            select(Job).where(Job.clip_id == clip_id, Job.status.in_(LIVE_STATUSES))
        )
        if existing is not None:
            log.info("clip %s already has job %s (%s)", clip_id, existing.id, existing.status)
            return existing

        job = Job(kind=kind, clip_id=clip_id, max_attempts=max_attempts)
        db.add(job)
        db.commit()
        return job
    except Exception:  # noqa: BLE001 — the caller decides how to degrade
        log.exception("could not enqueue work for clip %s", clip_id)
        db.rollback()
        return None


# ---------------------------------------------------------------- consuming

def claim(db: Session, worker: str) -> Job | None:
    """Take the next runnable job, or None. Concurrency-safe.

    SKIP LOCKED is what lets several workers poll the same table without
    serialising on the first row.
    """
    try:
        job = db.scalar(
            select(Job)
            .where(Job.status == "queued", Job.run_after <= _now())
            .order_by(Job.run_after, Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        job.status = "running"
        job.attempts += 1
        job.locked_by = worker
        job.locked_at = _now()
        db.commit()
        return job
    except Exception:  # noqa: BLE001
        log.exception("claim failed")
        db.rollback()
        return None


def heartbeat(db: Session, job_id: uuid.UUID) -> None:
    """Say the job is still alive, so its lock is not considered stale."""
    try:
        db.execute(update(Job).where(Job.id == job_id).values(locked_at=_now()))
        db.commit()
    except Exception:  # noqa: BLE001 — a missed beat is not fatal
        log.warning("heartbeat failed for job %s", job_id)
        db.rollback()


def finish(db: Session, job_id: uuid.UUID, error: str | None = None) -> None:
    """Mark a job done, or schedule a retry, or give up.

    Giving up is not silent: the clip is failed with an honest message so the
    user can retry for free, rather than watching a spinner forever.
    """
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        if error is None:
            job.status, job.error = "done", None
            job.finished_at = _now()
        elif job.attempts < job.max_attempts:
            job.status = "queued"
            job.error = error[:500]
            job.run_after = _now() + RETRY_BACKOFF
            job.locked_by = job.locked_at = None
            log.warning("job %s failed (%s); retrying in %ss",
                        job_id, error[:120], int(RETRY_BACKOFF.total_seconds()))
        else:
            job.status, job.error = "failed", error[:500]
            job.finished_at = _now()
            _fail_clip(db, job.clip_id,
                       "Generation did not complete. Your allowance was not "
                       "used — retry for free.")
        db.commit()
    except Exception:  # noqa: BLE001
        log.exception("could not finish job %s", job_id)
        db.rollback()


def release(db: Session, job_id: uuid.UUID) -> None:
    """Put a claimed job back, without counting a failure.

    Used on graceful shutdown: the deploy is our doing, not the job's fault,
    so it should not consume one of its attempts.
    """
    try:
        job = db.get(Job, job_id)
        if job is None or job.status != "running":
            return
        job.status = "queued"
        job.attempts = max(0, job.attempts - 1)
        job.locked_by = job.locked_at = None
        job.run_after = _now()
        db.commit()
        log.info("released job %s back to the queue", job_id)
    except Exception:  # noqa: BLE001
        log.exception("could not release job %s", job_id)
        db.rollback()


def reclaim_stale(db: Session) -> int:
    """Return jobs whose worker died to the queue. Returns how many."""
    try:
        cutoff = _now() - STALE_AFTER
        stale = db.scalars(
            select(Job).where(Job.status == "running", Job.locked_at < cutoff)
        ).all()
        for job in stale:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.error = "worker died and no attempts remained"
                job.finished_at = _now()
                _fail_clip(db, job.clip_id,
                           "Generation was interrupted. Your allowance was not "
                           "used — retry for free.")
            else:
                job.status = "queued"
                job.locked_by = job.locked_at = None
                job.run_after = _now()
        if stale:
            db.commit()
            log.warning("reclaimed %d stale job(s)", len(stale))
        return len(stale)
    except Exception:  # noqa: BLE001
        log.exception("reclaiming stale jobs failed")
        db.rollback()
        return 0


def _fail_clip(db: Session, clip_id: uuid.UUID | None, message: str) -> None:
    """Leave the clip in a state the user can act on."""
    if clip_id is None:
        return
    from ..models import Clip

    clip = db.get(Clip, clip_id)
    if clip is not None and clip.status not in ("ready", "failed"):
        clip.status = "failed"
        clip.error = message
        clip.current_step = None


def depth(db: Session) -> dict:
    """Queue sizes, for the health endpoint."""
    from sqlalchemy import func

    rows = db.execute(
        select(Job.status, func.count()).group_by(Job.status)
    ).all()
    counts = {status: count for status, count in rows}
    return {status: counts.get(status, 0) for status in ("queued", "running", "done", "failed")}
