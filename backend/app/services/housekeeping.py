"""Scheduled cleanup — `python -m app.services.housekeeping`.

Two jobs, both safe to run repeatedly and safe to skip:

1. **Purge scratch.** A 15s clip leaves ~38 MB of working files (per-scene
   clips, normalised copies, the pre-branding cut, rejected keyframes) against
   ~14 MB worth keeping. Without this the disk fills at roughly 3.6x the rate
   the product actually needs.

2. **Release stuck jobs.** Generation runs on a background thread, so a deploy
   or a crash mid-job leaves a clip pinned in a generating status forever: the
   UI spins, and the user cannot retry because the clip never reaches `failed`.
   Anything past the timeout is marked failed with an honest message, which
   restores the free-retry path (BR-09).

Run it from cron on the droplet, hourly:

    0 * * * * cd /opt/banter-clips/backend && .venv/bin/python -m app.services.housekeeping
"""

from __future__ import annotations

import logging
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import GENERATION_STAGES, Clip
from . import storage

log = logging.getLogger("banter.housekeeping")

# Longest plausible real run: 12 scenes x ~2 min of animation, plus slack.
STUCK_AFTER = timedelta(minutes=45)

STUCK_MESSAGE = (
    "Generation was interrupted before it finished. Your allowance was not "
    "used — retry for free."
)


def release_stuck_clips(now: datetime | None = None) -> int:
    """Fail clips that stopped making progress. Returns how many."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - STUCK_AFTER
    released = 0
    db = SessionLocal()
    try:
        stuck = db.scalars(
            select(Clip).where(
                Clip.status.in_(("queued", *GENERATION_STAGES)),
                Clip.created_at < cutoff,
            )
        ).all()
        for clip in stuck:
            clip.status = "failed"
            clip.error = STUCK_MESSAGE
            clip.current_step = None
            released += 1
        if released:
            db.commit()
            log.info("released %d stuck clip(s)", released)
    except Exception:  # noqa: BLE001 — housekeeping never takes the app down
        log.exception("could not release stuck clips")
    finally:
        db.close()
    return released


def purge_scratch(days: int | None = None) -> int:
    """Delete expired working files. Returns how many were removed."""
    days = days if days is not None else int(getattr(settings, "SCRATCH_RETENTION_DAYS", 7))
    removed = 0
    try:
        removed += storage.get().purge_scratch(days)
    except Exception:  # noqa: BLE001
        log.exception("purging stored scratch failed")

    # The pipeline's working directory is local even when storage is remote.
    work_root = Path(settings.MEDIA_DIR).parent / "work"
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    if work_root.exists():
        for job_dir in work_root.iterdir():
            try:
                if job_dir.is_dir() and job_dir.stat().st_mtime < cutoff:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    removed += 1
            except OSError:
                log.warning("could not remove %s", job_dir)
    return removed


def purge_evidence(days: int | None = None) -> int:
    """Delete keyframes for clips older than the evidence window.

    Driven from the clips table rather than from object mtimes, because
    Supabase Storage has no lifecycle rules and no cheap "list everything
    older than X". The deliverable and its poster are untouched — only the
    per-scene keyframes, which exist to explain a render, not to serve one.
    """
    days = days or storage.RETENTION_DAYS["evidence"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    db = SessionLocal()
    try:
        store = storage.get()
        stale = db.scalars(
            select(Clip).where(
                Clip.completed_at.is_not(None),
                Clip.completed_at < cutoff,
            )
        ).all()
        for clip in stale:
            prefix = storage.clip_prefix(clip.user_id, clip.id)
            provenance = clip.provenance or {}
            for scene in provenance.get("scenes", []):
                try:
                    store.delete(f"{prefix}/scene{scene.get('index')}_keyframe.jpg")
                    removed += 1
                except Exception:  # noqa: BLE001 — best effort per object
                    pass
    except Exception:  # noqa: BLE001
        log.exception("purging evidence failed")
    finally:
        db.close()
    return removed


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    released = release_stuck_clips()
    removed = purge_scratch()
    evidence = purge_evidence()
    print(f"released {released} stuck clip(s); removed {removed} expired item(s); "
          f"purged {evidence} keyframe(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
