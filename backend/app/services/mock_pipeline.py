"""Mock generation — the real pipeline's shape, none of its spend.

This walks a clip through exactly the stages the real workflow walks, emitting
exactly the progress lines the real runner emits, at roughly the timings we
measured ($2.41 / 4m30s for a 15s NBA clip). Nothing is generated: no model is
called, no image or video is produced, and the finished clip points at the
pre-rendered demo MP4.

Why it exists: the honest way to review the *flow* — the enhancer questions,
the step sequence, the pacing, what a user sees while waiting — without
spending money on every UI iteration. The step text is derived from the real
plan whenever a plan can be built for free (the planner falls back to a
deterministic template with no API key), so the names on screen are the names
the real run would use.

`PIPELINE_MODE=mock` selects it. Timings are scaled by MOCK_SPEED so a review
pass takes seconds rather than minutes.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from datetime import datetime, timezone

from ..config import settings
from ..db import SessionLocal
from ..models import GENERATION_STAGES, Clip

log = logging.getLogger("banter.mock")

GRADIENTS = [
    "linear-gradient(160deg,#7b2ff7,#c13584)",
    "linear-gradient(160deg,#22d3ee,#3d2c8d)",
    "linear-gradient(160deg,#34e27a,#0f5132)",
    "linear-gradient(160deg,#f0546c,#7b2ff7)",
]

FAIL_MARKER = "[fail]"

# Measured against real runs, in seconds, before MOCK_SPEED scaling.
REAL_TIMINGS = {
    "plan": 6.0,          # one gpt-4.1 call
    "cast": 1.5,
    "keyframe": 12.0,     # one Grok still + one vision review
    "animate": 95.0,      # one Grok clip, the dominant cost
    "assemble": 8.0,      # ffmpeg, scales with scene count
    "validate": 2.0,
}
# One scene in ~20 keyframe attempts came back needing a retry in real runs;
# showing that occasionally keeps the mock honest about what users will see.
RETRY_CHANCE = 0.25


def _sleep(seconds: float) -> None:
    speed = max(0.01, float(getattr(settings, "MOCK_SPEED", 12.0)))
    time.sleep(seconds / speed)


def run_mock_job(clip_id: uuid.UUID) -> None:
    """Drive one Clip row through a simulated run. Never raises."""
    db = SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        if clip is None:
            return
        force_fail = FAIL_MARKER in (clip.take or "").lower()
        plan, scene_count = _free_plan(clip)

        def stage(name: str) -> None:
            clip.status = name
            clip.stage_index = GENERATION_STAGES.index(name)
            db.commit()

        def say(text: str, kind: str = "step") -> None:
            # The row is the only place progress can live: the API runs
            # several workers and a poll may land on any of them.
            clip.current_step = text
            db.commit()

        # 1. planning ---------------------------------------------------
        stage("planning_story")
        say("Writing your script")
        _sleep(REAL_TIMINGS["plan"])
        cast = ", ".join(m.name for m in plan.cast) if plan else "the cast"
        say(f"Casting {cast}")

        # 2-3. voices and characters ------------------------------------
        stage("creating_voice")
        say("Finding their voices")
        _sleep(REAL_TIMINGS["cast"])

        stage("designing_characters")
        say("Designing the characters")
        _sleep(REAL_TIMINGS["cast"])
        say("Locking in how they look")

        # 4. keyframes ---------------------------------------------------
        stage("generating_scenes")
        for index in range(scene_count):
            attempts = 2 if random.random() < RETRY_CHANCE else 1
            for attempt in range(1, attempts + 1):
                say(f"Designing scene {index + 1} of {scene_count}")
                _sleep(REAL_TIMINGS["keyframe"])
                if attempt < attempts:
                    say(f"Polishing scene {index + 1}", kind="warn")
            if force_fail and index == 0:
                clip.status = "failed"
                clip.error = (
                    "Scene generation did not pass validation after its bounded "
                    "retry. Your allowance was not used — retry for free."
                )
                db.commit()
                say("Couldn't finish this one", kind="error")
                return
            say(f"Scene {index + 1} looks good", kind="ok")

        # 5. animation ---------------------------------------------------
        stage("animating_scenes")
        for index in range(scene_count):
            say(f"Bringing scene {index + 1} to life")
            _sleep(REAL_TIMINGS["animate"])
            say(f"Scene {index + 1} is alive", kind="ok")

        # 6-7. assemble and validate -------------------------------------
        stage("assembling_video")
        say("Cutting it together and adding captions")
        _sleep(REAL_TIMINGS["assemble"])

        stage("validating")
        say("Final checks")
        _sleep(REAL_TIMINGS["validate"])

        target = clip.duration_target or 15
        clip.status = "ready"
        # Demo output: the sample video, not this user's take. The flag
        # is what stops it being published to a real account.
        clip.is_simulated = True
        clip.error = None
        clip.duration_seconds = float(target)
        clip.video_url = f"{settings.API_BASE_URL}/media/demo.mp4"
        clip.thumb_gradient = random.choice(GRADIENTS)
        clip.completed_at = datetime.now(timezone.utc)
        db.commit()
        say("Your clip is ready", kind="ok")
    except Exception as exc:  # noqa: BLE001 — job boundary
        log.exception("mock job %s crashed", clip_id)
        try:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "failed"
                clip.error = str(exc)[:500]
                db.commit()
        except Exception:  # noqa: BLE001
            log.exception("could not record failure for %s", clip_id)
    finally:
        db.close()


def _free_plan(clip: Clip):
    """Build a real plan without spending anything.

    `planner.build_plan(..., client=None)` uses the deterministic template, so
    the cast names and scene count on screen are the ones the real pipeline
    would use for this take — no API call, no cost.
    """
    try:
        from ..video import defaults, planner

        resolved = defaults.resolve(clip.take, clip.sport, clip.tone, clip.duration_target)
        return planner.build_plan(resolved, client=None), resolved.scene_count
    except Exception:  # noqa: BLE001 — the mock must never depend on the pipeline
        log.exception("mock could not build a free plan; using a stub")
        return None, 2


