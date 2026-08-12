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
from . import progress

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
    progress.start(clip_id)
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
            progress.push(clip_id, text, kind)

        cost = 0.0

        # 1. planning ---------------------------------------------------
        stage("planning_story")
        say(f"writing the script — {clip.sport}, {clip.tone}, "
            f"{clip.duration_target}s in {scene_count} scenes")
        _sleep(REAL_TIMINGS["plan"])
        cast = ", ".join(m.name for m in plan.cast) if plan else "the cast"
        title = plan.title if plan else clip.take[:48]
        say(f'script ready: "{title}"; cast {cast}')

        # 2-3. voices and characters ------------------------------------
        stage("creating_voice")
        say("assigning voices — consecutive scenes never share a speaker")
        _sleep(REAL_TIMINGS["cast"])

        stage("designing_characters")
        say(f"resolving {cast} from the character catalog")
        _sleep(REAL_TIMINGS["cast"])
        say("attaching reference stills for identity")

        # 4. keyframes ---------------------------------------------------
        stage("generating_scenes")
        speakers = _speakers(plan, scene_count)
        for index in range(scene_count):
            who = speakers[index]
            attempts = 2 if random.random() < RETRY_CHANCE else 1
            for attempt in range(1, attempts + 1):
                say(f"scene {index + 1}/{scene_count}: keyframe attempt {attempt}/3 "
                    f"for {who} with reference stills")
                _sleep(REAL_TIMINGS["keyframe"])
                cost += 0.05
                if attempt < attempts:
                    say(f"scene {index + 1}: rejected — text visible on kit or "
                        f"signage; regenerating", kind="warn")
            if force_fail and index == 0:
                clip.status = "failed"
                clip.error = (
                    "Scene generation did not pass validation after its bounded "
                    "retry. Your allowance was not used — retry for free."
                )
                db.commit()
                say("generation failed after bounded retries", kind="error")
                return
            say(f"scene {index + 1}: keyframe approved (${cost:.2f} spent so far)",
                kind="ok")

        # 5. animation ---------------------------------------------------
        stage("animating_scenes")
        per_scene = round((clip.duration_target or 15) / max(1, scene_count))
        for index in range(scene_count):
            say(f"scene {index + 1}/{scene_count}: animating {per_scene}s at "
                f"{getattr(settings, 'VIDEO_RESOLUTION', '720p')} — this is the "
                f"slow one, ~1-2 min")
            started = time.time()
            _sleep(REAL_TIMINGS["animate"])
            cost += 1.12
            took = REAL_TIMINGS["animate"] if time.time() - started >= 0 else 0
            say(f"scene {index + 1}: animated in {took:.0f}s "
                f"(${cost:.2f} spent so far)", kind="ok")

        # 6-7. assemble and validate -------------------------------------
        stage("assembling_video")
        say(f"joining {scene_count} clips, matching loudness, burning "
            f"{scene_count} captions and the disclosure")
        _sleep(REAL_TIMINGS["assemble"])

        stage("validating")
        say("checking duration, dimensions, codecs and audio")
        _sleep(REAL_TIMINGS["validate"])

        target = clip.duration_target or 15
        clip.status = "ready"
        clip.error = None
        clip.duration_seconds = float(target)
        clip.video_url = f"{settings.API_BASE_URL}/media/demo.mp4"
        clip.thumb_gradient = random.choice(GRADIENTS)
        clip.completed_at = datetime.now(timezone.utc)
        db.commit()
        say(f"done — {target}s, 1080x1920, ${cost:.2f} (simulated)", kind="ok")
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


def _speakers(plan, scene_count: int) -> list[str]:
    if plan and plan.cast:
        names = []
        for scene in plan.scenes[:scene_count]:
            member = plan.speaker_for(scene)
            names.append(member.name if member else plan.cast[0].name)
        if len(names) >= scene_count:
            return names
    return ["the subject"] * scene_count
