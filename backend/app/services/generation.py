"""Dummy generation pipeline.

Real video generation is still being decided (see VIDEO-PIPELINE-SPEC.md and
the provider bake-off). Until then this walks a clip through the honest BR-07
stages on a background thread, then attaches the pre-rendered demo MP4.

The job state machine, allowance accounting, retry semantics, and API shape
are all real — swapping this file for the actual pipeline is the only change
needed later (same statuses, same columns).
"""

import random
import threading
import time
import uuid
from datetime import datetime, timezone

from ..config import settings
from ..db import SessionLocal
from ..models import GENERATION_STAGES, Clip

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
        clip.error = None
        target = clip.duration_target or 15
        clip.duration_seconds = round(random.uniform(max(target - 3, 8), target), 1)
        clip.video_url = f"{settings.API_BASE_URL}/media/demo.mp4"
        clip.thumb_gradient = random.choice(GRADIENTS)
        clip.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def start_generation(clip_id: uuid.UUID) -> None:
    """Kick off generation for a clip.

    PIPELINE_MODE picks the implementation:

      dummy  walk the stages on a timer, attach the demo clip (default)
      mock   walk the REAL step sequence with real pacing, generate nothing
      real   run the workflow in app/video, spending real money

    The job state machine, allowance accounting and API shape are identical
    in all three, so switching is a config change and rollback is instant.
    """
    mode = str(getattr(settings, "PIPELINE_MODE", "dummy")).lower()
    if mode == "real":
        from ..video import run_clip_job

        target = run_clip_job
    elif mode == "mock":
        # Same stages, same progress lines, same pacing — nothing generated.
        # Lets the whole flow be reviewed without spending on every iteration.
        from .mock_pipeline import run_mock_job

        target = run_mock_job
    else:
        target = _run_job
    threading.Thread(target=target, args=(clip_id,), daemon=True).start()
