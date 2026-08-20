"""Generation worker — `python -m app.worker`.

Runs in its own process, separate from the API. That separation is the point:
restarting or deploying the API no longer interrupts a render, and a render
that pins a CPU for four minutes no longer competes with request handling.

The loop is deliberately dull: claim one job, run it, mark it, repeat. A
heartbeat thread refreshes the lock while the job runs so a long animation is
not mistaken for a dead worker.

On SIGTERM (systemd stop, deploy) it stops claiming, lets the current job
finish if it can, and puts it back on the queue otherwise — without counting
an attempt, because the interruption was our doing.

    python -m app.worker                # run until stopped
    python -m app.worker --once         # drain one job and exit (for cron/CI)
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time

from .db import SessionLocal
from .services import jobs

log = logging.getLogger("banter.worker")

POLL_SECONDS = 2.0
# How often to sweep for jobs whose worker died. Cheap; a few times a minute
# is plenty and keeps a crashed render from stranding for long.
RECLAIM_EVERY = 60.0


class Worker:
    def __init__(self, name: str | None = None):
        self.name = name or jobs.worker_name()
        self.stopping = threading.Event()
        self.current_job_id = None

    # ---------------------------------------------------------- lifecycle

    def install_signals(self) -> None:
        def stop(signum, _frame):
            log.info("signal %s received; finishing current work and stopping", signum)
            self.stopping.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, stop)

    def _heartbeat_loop(self, job_id) -> None:
        """Keep the lock fresh so a long render is not reclaimed under us."""
        db = SessionLocal()
        try:
            while not self._job_done.wait(jobs.HEARTBEAT_SECONDS):
                jobs.heartbeat(db, job_id)
        finally:
            db.close()

    # ------------------------------------------------------------ running

    def run_job(self, job) -> None:
        """Execute one job. Never raises; failure is recorded on the row."""
        from .services.generation import run_for_clip

        self.current_job_id = job.id
        self._job_done = threading.Event()
        beat = threading.Thread(target=self._heartbeat_loop, args=(job.id,), daemon=True)
        beat.start()

        db = SessionLocal()
        started = time.time()
        try:
            log.info("job %s starting (clip %s, attempt %d/%d)",
                     job.id, job.clip_id, job.attempts, job.max_attempts)
            run_for_clip(job.clip_id)
            jobs.finish(db, job.id)
            log.info("job %s done in %.1fs", job.id, time.time() - started)
        except Exception as exc:  # noqa: BLE001 — job boundary
            log.exception("job %s crashed", job.id)
            jobs.finish(db, job.id, error=str(exc))
        finally:
            self._job_done.set()
            self.current_job_id = None
            db.close()

    def loop(self, once: bool = False) -> int:
        db = SessionLocal()
        last_reclaim = 0.0
        handled = 0
        log.info("worker %s ready", self.name)
        try:
            while not self.stopping.is_set():
                now = time.time()
                if now - last_reclaim > RECLAIM_EVERY:
                    jobs.reclaim_stale(db)
                    last_reclaim = now

                job = jobs.claim(db, self.name)
                if job is None:
                    if once:
                        break
                    self.stopping.wait(POLL_SECONDS)
                    continue

                # A stop that arrives between claiming and starting should not
                # cost the job an attempt.
                if self.stopping.is_set():
                    jobs.release(db, job.id)
                    break

                self.run_job(job)
                handled += 1
                if once:
                    break
        finally:
            db.close()
        log.info("worker %s stopped after %d job(s)", self.name, handled)
        return handled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BanterClips generation worker")
    parser.add_argument("--once", action="store_true", help="drain one job and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Additive column migrations, same as the API's startup. The worker can
    # win the race after a deploy and select model columns the API has not
    # added yet; applying here (idempotent, never raises) closes that window.
    # create_all covers brand-new tables (e.g. catalog_characters) the same way.
    from . import db_migrate
    from .db import Base, engine

    try:
        Base.metadata.create_all(bind=engine)
    except Exception:  # noqa: BLE001 — boot must survive; the API creates them too
        logging.getLogger("banter.worker").exception("create_all failed; continuing")
    db_migrate.apply()
    worker = Worker()
    worker.install_signals()
    worker.loop(once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
