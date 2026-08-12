"""Dummy generation pipeline.

Real video generation is still being decided (see VIDEO-PIPELINE-SPEC.md and
the provider bake-off). Until then this walks a clip through the honest BR-07
stages on a background thread, then attaches the pre-rendered demo MP4.

The job state machine, allowance accounting, retry semantics, and API shape
are all real — swapping this file for the actual pipeline is the only change
needed later (same statuses, same columns).
"""

import logging
import random
import threading
import time
import uuid
from datetime import datetime, timezone

from ..config import settings
from ..db import SessionLocal
from ..models import GENERATION_STAGES, Clip
from . import jobs

log = logging.getLogger("banter.generation")

GRADIENTS = [
    "linear-gradient(160deg,#7b2ff7,#c13584)",
    "linear-gradient(160deg,#22d3ee,#3d2c8d)",
    "linear-gradient(160deg,#34e27a,#0f5132)",
    "linear-gradient(160deg,#f0546c,#7b2ff7)",
]

# Typing "[fail]" anywhere in the take forces a failure — lets anyone demo the
# failed state + free retry (BR-07/BR-09) without waiting for a real error.
FAIL_MARKER = "[fail]"


def _run_job(clip_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        if clip is None:
            return
        force_fail = FAIL_MARKER in clip.take.lower()

        for i, stage in enumerate(GENERATION_STAGES):
            clip.status = stage
            clip.stage_index = i
            db.commit()
            time.sleep(settings.STAGE_SECONDS)

            # Fail while "generating scenes" if the take asks for it.
            if force_fail and stage == "generating_scenes":
                clip.status = "failed"
                clip.error = (
                    "Scene generation did not pass validation after its bounded "
                    "retry. Your allowance was not used — retry for free."
                )
                db.commit()
                return

        clip.status = "ready"
        # Demo output: the sample video, not this user's take. The flag
        # is what stops it being published to a real account.
        clip.is_simulated = True
        clip.error = None
        target = clip.duration_target or 15
        clip.duration_seconds = round(random.uniform(max(target - 3, 8), target), 1)
        clip.video_url = f"{settings.API_BASE_URL}/media/demo.mp4"
        clip.thumb_gradient = random.choice(GRADIENTS)
        clip.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _is_simulated(clip_id: uuid.UUID) -> bool:
    """Read the flag set at creation. A lookup failure means 'not simulated'."""
    db = SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        return bool(clip is not None and clip.is_simulated)
    except Exception:  # noqa: BLE001
        return False
    finally:
        db.close()


def run_for_clip(clip_id: uuid.UUID) -> None:
    """Actually generate one clip, synchronously, in this process.

    PIPELINE_MODE picks the implementation:

      dummy  walk the stages on a timer, attach the demo clip (default)
      mock   walk the REAL step sequence with real pacing, generate nothing
      real   run the workflow in app/video, spending real money

    The job state machine, allowance accounting and API shape are identical
    in all three, so switching is a config change and rollback is instant.
    """
    # A [mock] take is simulated whatever the deployment is set to, so the
    # flow can be demonstrated on production without spending anything.
    if _is_simulated(clip_id):
        from .mock_pipeline import run_mock_job

        run_mock_job(clip_id)
        return

    mode = str(getattr(settings, "PIPELINE_MODE", "dummy")).lower()
    if mode == "real":
        from ..video import run_clip_job

        run_clip_job(clip_id)
    elif mode == "mock":
        # Same stages, same progress lines, same pacing — nothing generated.
        from .mock_pipeline import run_mock_job

        run_mock_job(clip_id)
    else:
        _run_job(clip_id)


def start_generation(clip_id: uuid.UUID) -> None:
    """Get a clip rendered — durably in production, inline in development.

    QUEUE_MODE=postgres (production) writes a row and returns; a separate
    worker process picks it up. That is what makes a deploy safe: the API can
    restart mid-render without losing the job, and the render does not compete
    with request handling for CPU.

    QUEUE_MODE=thread keeps the old in-process behaviour so `uvicorn` alone is
    still a complete development environment with nothing else to run.
    """
    mode = str(getattr(settings, "QUEUE_MODE", "thread")).lower()

    if mode == "postgres":
        db = SessionLocal()
        try:
            if jobs.enqueue(db, clip_id) is not None:
                return
            log.error("could not queue clip %s; running it in-process instead", clip_id)
        finally:
            db.close()

    threading.Thread(target=run_for_clip, args=(clip_id,), daemon=True).start()
