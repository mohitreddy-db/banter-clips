"""Queue behaviour, against a real Postgres.

These are the properties that make a durable queue worth having, so each test
is named for the failure it prevents. Requires the local database; skips
cleanly if it is not reachable.

    .venv/bin/python tests/test_queue.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Clip, Job, User  # noqa: E402
from app.services import jobs  # noqa: E402

TEST_EMAIL = "queue-test@banterclips.test"


def _reachable() -> bool:
    try:
        db = SessionLocal()
        db.execute(select(1))
        db.close()
        return True
    except Exception:  # noqa: BLE001
        return False


def _user(db) -> User:
    user = db.scalar(select(User).where(User.email == TEST_EMAIL))
    if user is None:
        user = User(email=TEST_EMAIL)
        db.add(user)
        db.commit()
    return user


def _clip(db) -> Clip:
    clip = Clip(
        user_id=_user(db).id,
        take="A queue test take that is long enough to store.",
        sport="NBA", tone="Funny", duration_target=15,
    )
    db.add(clip)
    db.commit()
    return clip


def _cleanup(db) -> None:
    user = db.scalar(select(User).where(User.email == TEST_EMAIL))
    if user is None:
        return
    clip_ids = [c.id for c in db.scalars(select(Clip).where(Clip.user_id == user.id)).all()]
    if clip_ids:
        db.execute(delete(Job).where(Job.clip_id.in_(clip_ids)))
        db.execute(delete(Clip).where(Clip.id.in_(clip_ids)))
    db.commit()


def test_a_job_survives_as_a_row():
    """The whole point: work outlives the process that requested it."""
    db = SessionLocal()
    try:
        clip = _clip(db)
        job = jobs.enqueue(db, clip.id)
        assert job is not None and job.status == "queued"
        # Read it back through a different session, as a worker would.
        other = SessionLocal()
        try:
            assert other.get(Job, job.id) is not None
        finally:
            other.close()
    finally:
        _cleanup(db)
        db.close()


def test_the_same_clip_is_never_queued_twice():
    """A double-clicked button must not bill two renders."""
    db = SessionLocal()
    try:
        clip = _clip(db)
        first = jobs.enqueue(db, clip.id)
        second = jobs.enqueue(db, clip.id)
        assert first.id == second.id
        live = db.scalars(
            select(Job).where(Job.clip_id == clip.id, Job.status.in_(jobs.LIVE_STATUSES))
        ).all()
        assert len(live) == 1
    finally:
        _cleanup(db)
        db.close()


def test_claiming_marks_it_running_and_counts_the_attempt():
    db = SessionLocal()
    try:
        clip = _clip(db)
        jobs.enqueue(db, clip.id)
        job = jobs.claim(db, "worker-a")
        assert job is not None
        assert job.status == "running" and job.attempts == 1
        assert job.locked_by == "worker-a" and job.locked_at is not None
    finally:
        _cleanup(db)
        db.close()


def test_two_workers_never_get_the_same_job():
    """SKIP LOCKED is what makes a second worker safe to add."""
    db_a, db_b = SessionLocal(), SessionLocal()
    try:
        clip = _clip(db_a)
        jobs.enqueue(db_a, clip.id)
        first = jobs.claim(db_a, "worker-a")
        second = jobs.claim(db_b, "worker-b")
        assert first is not None
        assert second is None or second.id != first.id
    finally:
        _cleanup(db_a)
        db_a.close()
        db_b.close()


def test_a_failure_is_retried_then_gives_up_honestly():
    """A clip must never sit in a generating state forever."""
    db = SessionLocal()
    try:
        clip = _clip(db)
        jobs.enqueue(db, clip.id, max_attempts=2)

        job = jobs.claim(db, "w")
        jobs.finish(db, job.id, error="provider timeout")
        db.refresh(job)
        assert job.status == "queued"          # retry scheduled
        assert job.run_after > job.created_at  # with backoff

        job.run_after = job.created_at         # make it claimable now
        db.commit()
        job = jobs.claim(db, "w")
        jobs.finish(db, job.id, error="provider timeout again")
        db.refresh(job)
        assert job.status == "failed"

        db.refresh(clip)
        assert clip.status == "failed"
        assert "retry for free" in (clip.error or "").lower()
    finally:
        _cleanup(db)
        db.close()


def test_a_dead_worker_does_not_strand_the_job():
    """A killed worker is the normal case for a deploy, not an exception."""
    db = SessionLocal()
    try:
        clip = _clip(db)
        jobs.enqueue(db, clip.id, max_attempts=3)
        job = jobs.claim(db, "doomed-worker")

        # Pretend its last heartbeat was long ago.
        job.locked_at = jobs._now() - jobs.STALE_AFTER - timedelta(minutes=1)
        db.commit()

        assert jobs.reclaim_stale(db) == 1
        db.refresh(job)
        assert job.status == "queued" and job.locked_by is None
    finally:
        _cleanup(db)
        db.close()


def test_graceful_shutdown_does_not_cost_an_attempt():
    """Our deploy is not the job's fault."""
    db = SessionLocal()
    try:
        clip = _clip(db)
        jobs.enqueue(db, clip.id)
        job = jobs.claim(db, "w")
        assert job.attempts == 1
        jobs.release(db, job.id)
        db.refresh(job)
        assert job.status == "queued" and job.attempts == 0
    finally:
        _cleanup(db)
        db.close()


def test_depth_reports_every_status():
    db = SessionLocal()
    try:
        depth = jobs.depth(db)
        assert set(depth) == {"queued", "running", "done", "failed"}
        assert all(isinstance(v, int) for v in depth.values())
    finally:
        db.close()


# ---- regenerate-with-different-options, at the script approval gate --------

def _script_clip(db, *, plan="free", balance=200):
    """A clip parked at the approval gate, plus its owner in a known state."""
    user = _user(db)
    user.plan = plan
    user.credits = balance
    clip = Clip(
        user_id=user.id,
        take="A script options test take that is long enough.",
        sport="NBA", tone="Funny", duration_target=15, resolution="720p",
        status="script_ready", credits_quoted=60,
        script={"title": "t", "scenes": [{"seconds": 4.0, "line": "hi", "action": "waves"}]},
    )
    db.add(clip)
    db.commit()
    return user, clip


def _quiet_generation():
    """Swap the router's start_generation for a noop; returns the original."""
    from app.routers import clips as clips_router

    real = clips_router.start_generation
    clips_router.start_generation = lambda cid: None
    return clips_router, real


def test_regenerate_with_new_options_requotes_and_updates_the_clip():
    """Changing tone/length/quality at the approval gate must re-quote the
    video at the exact menu price — and still charge nothing (rule 3)."""
    from app.services import credits

    db = SessionLocal()
    clips_router, real = _quiet_generation()
    try:
        user, clip = _script_clip(db, plan="creator", balance=500)
        clips_router.regenerate_script(
            clip.id,
            clips_router.ScriptRegenerate(tone="Roast", duration=30, resolution="1080p"),
            user, db)
        db.refresh(clip)
        assert (clip.tone, clip.duration_target, clip.resolution) == ("Roast", 30, "1080p")
        assert clip.credits_quoted == credits.video_price(db, 30, "1080p")
        assert clip.status == "queued" and clip.script is None
        db.refresh(user)
        assert user.credits == 500  # charge-on-completion: wallet untouched
    finally:
        clips_router.start_generation = real
        _cleanup(db)
        db.close()


def test_regenerate_options_respect_plan_gates_and_change_nothing_on_refusal():
    """A Free user asking for 30s or 1080p at the gate is told to upgrade,
    and the clip stays exactly as it was — same script, same quote."""
    from fastapi import HTTPException

    db = SessionLocal()
    clips_router, real = _quiet_generation()
    try:
        user, clip = _script_clip(db, plan="free", balance=500)
        for body in (clips_router.ScriptRegenerate(duration=30),
                     clips_router.ScriptRegenerate(resolution="1080p")):
            try:
                clips_router.regenerate_script(clip.id, body, user, db)
                raise AssertionError("expected a 403 upgrade_required")
            except HTTPException as exc:
                assert exc.status_code == 403
        db.refresh(clip)
        assert clip.status == "script_ready"
        assert (clip.duration_target, clip.resolution, clip.credits_quoted) == (15, "720p", 60)
    finally:
        clips_router.start_generation = real
        _cleanup(db)
        db.close()


def test_regenerate_options_check_the_balance_against_the_new_quote():
    """Upsizing past the wallet is refused with a top-up 402 — but a plain
    rewrite (no option change) stays free even on a low balance."""
    from fastapi import HTTPException
    from app.services import credits

    db = SessionLocal()
    clips_router, real = _quiet_generation()
    try:
        needed = credits.video_price(db, 15, "1080p")
        user, clip = _script_clip(db, plan="creator", balance=needed - 1)
        try:
            clips_router.regenerate_script(
                clip.id, clips_router.ScriptRegenerate(resolution="1080p"), user, db)
            raise AssertionError("expected a 402 insufficient_credits")
        except HTTPException as exc:
            assert exc.status_code == 402
        db.refresh(clip)
        assert clip.status == "script_ready" and clip.resolution == "720p"

        clips_router.regenerate_script(
            clip.id, clips_router.ScriptRegenerate(feedback="less cringe"), user, db)
        db.refresh(clip)
        assert clip.status == "queued"  # rewriting itself never needs credits
    finally:
        clips_router.start_generation = real
        _cleanup(db)
        db.close()


if __name__ == "__main__":
    if not _reachable():
        print("database not reachable — skipping queue tests")
        sys.exit(0)
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {name}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
