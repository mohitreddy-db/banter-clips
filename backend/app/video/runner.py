"""Pipeline orchestration.

Contract: `generate_video` always returns a Result and never raises. If a
stage degrades, it substitutes and records a warning; only a genuinely
unrecoverable state (no ffmpeg, or not one usable scene) produces ok=False.

Degradation ladder, in order, per scene:

    real keyframe -> placeholder still
    real animation -> Ken Burns on the keyframe -> drop the scene

A job survives losing individual scenes. It fails only when nothing is left.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..config import settings
from . import (
    catalog, defaults, enhancer, media, planner, prompts, providers, research,
    review, shotwriter,
)
from .types import SceneAsset, VideoPlan

log = logging.getLogger("banter.video.runner")

# Names must match models.GENERATION_STAGES so the existing UI keeps working.
STAGE_PLANNING = "planning_story"
STAGE_VOICE = "creating_voice"
STAGE_CHARACTERS = "designing_characters"
STAGE_SCENES = "generating_scenes"
STAGE_ANIMATE = "animating_scenes"
STAGE_ASSEMBLE = "assembling_video"
STAGE_VALIDATE = "validating"

# Three, not two: the gate now hard-fails five distinct defects, and each
# retry is escalated with a correction targeting what actually failed. Two
# attempts left a rejected frame shipping into the final cut.
MAX_KEYFRAME_ATTEMPTS = 3

# Scenes are independent — separate prompts, separate files — so they render
# concurrently. Capped because every worker holds an HTTP connection to the
# provider and a render pins a core during ffmpeg; unbounded fan-out on a
# 12-scene job would be rude to both.
# Scene work is mostly waiting on the provider, so more workers than cores is
# fine — but each one can fall back to ffmpeg, and on a single-core box that
# is the difference between a slow site and an unreachable one. Follow the
# hardware: 1 vCPU -> 2, 4 vCPU -> 4.
MAX_PARALLEL_SCENES = max(2, min(4, (os.cpu_count() or 1) * 2))


class _Ledger:
    """Shared spend counter. `charge` is atomic and reports whether the job is
    still inside budget, so two workers cannot both see room for the last
    dollar and each spend it."""

    def __init__(self, budget: float):
        self.budget = budget
        self.spent = 0.0
        self._lock = threading.Lock()

    def charge(self, amount: float) -> float:
        with self._lock:
            self.spent += amount
            return self.spent

    def exhausted(self) -> bool:
        with self._lock:
            return self.spent >= self.budget


@dataclass
class Result:
    ok: bool = False
    video_path: Path | None = None
    poster_path: Path | None = None
    duration: float = 0.0
    resolution: str = ""
    cost_usd: float = 0.0
    plan: VideoPlan | None = None
    assets: list[SceneAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""

    def warn(self, message: str) -> None:
        log.warning("pipeline: %s", message)
        self.warnings.append(message)


def generate_video(
    take: object = None,
    sport: object = None,
    tone: object = None,
    seconds: object = None,
    *,
    work_dir: Path,
    out_path: Path,
    watermark: str | None = "BanterClips",
    on_stage=None,
    on_progress=None,
    brief: "enhancer.Brief | None" = None,
    resolution: str | None = None,
    plan: VideoPlan | None = None,
    budget: float | None = None,
) -> Result:
    """Run the whole pipeline. Never raises.

    `brief` is an already-enhanced brief (see `enhancer.enhance`), carrying a
    sharpened take, a fixed style preset and any choices the user made. Passing
    one skips re-enhancement; omitting it runs the raw inputs as before.

    `resolution` is the clip's requested output ("720p"/"1080p"); omitted, the
    VIDEO_RESOLUTION setting applies as before.
    """
    result = Result()
    resolution = resolution or getattr(settings, "VIDEO_RESOLUTION", "720p")
    result.resolution = resolution
    size = media.dims(resolution)
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if budget is None:
        budget = float(getattr(settings, "MAX_JOB_COST_USD", 8.0))

    def stage(name: str) -> None:
        if on_stage:
            try:
                on_stage(name)
            except Exception:  # noqa: BLE001 — reporting must not break the run
                log.exception("stage callback failed")

    def say(detail: str, public: str = "") -> None:
        """Fine-grained progress, in two registers.

        `detail` is for us — attempt counts, resolutions, running spend. It
        goes to the log and the CLI. `public` is what a customer should read:
        no costs, no retry counts, no internal vocabulary. The API only ever
        forwards `public`, so operational detail cannot leak into the product.
        """
        log.info("%s", detail)
        if on_progress:
            try:
                on_progress(detail, public or detail)
            except Exception:  # noqa: BLE001 — reporting must not break the run
                log.exception("progress callback failed")

    if not media.available():
        result.error = "ffmpeg and ffprobe are required but were not found on PATH"
        return result

    # ---------------------------------------------------------- 1. plan
    stage(STAGE_PLANNING)
    text = providers.text_client()
    if brief is None:
        resolved = defaults.resolve(take, sport, tone, seconds)
    else:
        resolved = enhancer.resolved_from(brief)
    if plan is not None:
        # Script approval flow: the user already read and approved this exact
        # plan — render it verbatim, never re-plan.
        say(f"rendering the approved script \"{plan.title}\" "
            f"({len(plan.scenes)} shots)", "Preparing your approved script")
    else:
        say(f"writing the script — {resolved.sport}, {resolved.tone}, "
            f"{resolved.seconds}s in {resolved.scene_count} shots",
            "Writing your script")
        from . import context

        plan = planner.build_plan(
            resolved, text, storyline=context.summarize(context.get_pack(resolved.take, resolved.sport))
        )
    say(f"script: \"{plan.title}\" ({plan.source}); "
        f"cast {', '.join(m.name for m in plan.cast)}",
        f"Casting {', '.join(m.name for m in plan.cast[:2])}")
    if brief is not None and brief.style:
        # A fixed preset beats a per-job invented style: it is the same look in
        # every scene, which is what keeps a multi-scene video consistent.
        plan.style = brief.style
    plan.disclosure = str(getattr(settings, "VIDEO_DISCLOSURE", "") or "")
    result.plan = plan
    if plan.source != "llm":
        result.warn(f"story plan came from the {plan.source} path")
    if str(getattr(settings, "SHOT_WRITER", "off")).lower() == "openai":
        say("directing the shots", "Framing the shots")
        bodies = shotwriter.write(plan, text)
        for scene in plan.scenes:
            scene.shot_prompt = bodies.get(scene.index, "")
        if bodies:
            say(f"shot writer described {len(bodies)}/{len(plan.scenes)} shots",
                "Framing the shots")
        else:
            result.warn("shot writer unavailable; using the assembled template")

    _write(work_dir / "plan.json", plan.to_dict())
    _write(work_dir / "input.json", resolved.to_dict())
    if brief is not None:
        _write(work_dir / "brief.json", brief.to_dict())

    # ------------------------------------------------- 2. voices / cast
    stage(STAGE_VOICE)
    speakers = {s.speaker_id for s in plan.scenes}
    if len(speakers) < min(2, len(plan.scenes)):
        result.warn("scenes share a speaker; voices may drift between clips")

    # -------------------------------------- 3. characters and references
    stage(STAGE_CHARACTERS)
    # The image provider and spend ledger exist from here (not stage 4):
    # discovering a new character may buy its reference stills, and that
    # spend must count against the same per-job ceiling as everything else.
    images = providers.image_provider()
    ledger = _Ledger(budget)
    references: dict[str, catalog.Character | None] = {}
    for member in plan.cast:
        if not member.wardrobe:
            member.wardrobe = "an authentic team kit with crest, name and number"
        char = catalog.get_character(member.id)
        if char is None and research.enabled() and research.looks_like_real_person(member.name):
            # Off-catalog cast: one web-search call buys a real description
            # before any image money is spent. Only names that read as a real
            # person are researched or persisted — a generic "random La Liga
            # defender" once came back dressed as an actual Barcelona player.
            # Distinct people stay distinct: the entry is keyed by this
            # member's own id, never merged into a lookalike.
            if research.enrich_member(member, plan.sport):
                result.warn(f"cast '{member.id}' enriched via web research")
                char = catalog.save_dynamic_character(member, plan.sport)
                autogen = str(getattr(settings, "CATALOG_AUTOGEN_REFS", "on")).lower() == "on"
                if (char is not None and autogen and not char.reference_paths()
                        and not isinstance(images, providers.StubImageProvider)
                        and not ledger.exhausted()):
                    say(f"building reference stills for {member.name}",
                        f"Studying {member.name}")
                    from . import catalog_build

                    ref_paths, ref_cost = catalog_build.build_character(char, images)
                    ledger.charge(ref_cost)
                    if ref_paths:
                        catalog.set_reference_images(char.id, ref_paths)
                        char = catalog.get_character(char.id)
        references[member.id] = char
    _write(work_dir / "cast.json", [
        {**m.__dict__,
         "reference_images": [str(p) for p in catalog.select_references(references.get(m.id))]}
        for m in plan.cast
    ])

    # ------------------------------------------------------ 4. keyframes
    stage(STAGE_SCENES)
    reviewer = providers.review_client()
    reviewer = reviewer if getattr(reviewer, "available", False) else None
    if isinstance(images, providers.StubImageProvider):
        # Placeholder gradients are not photographs and never will be. Judging
        # them wastes a review call and all three attempts on every scene.
        reviewer = None
    done_count = threading.Lock()
    finished = [0]
    total = len(plan.scenes)
    # Scene 0's delivered keyframe anchors every later scene's generation as
    # an extra reference image. Reviewed clips drifted BETWEEN scenes — a kit
    # changing clubs, a crowd changing colours — because scenes shared only
    # prompt text; a picture of the actual rendered world pins them together.
    venue_anchor: list[Path] = []

    def make_keyframe(scene) -> SceneAsset:
        """One scene's keyframe, start to finish. Runs on a worker thread."""
        asset = SceneAsset(index=scene.index)
        base_prompt = prompts.build_image_prompt(plan, scene)
        speaker = plan.speaker_for(scene)
        subject = (speaker or plan.cast[0]).name if plan.cast else "the subject"
        # Identity anchors for everyone the prompt says is in this shot, from
        # the same helper the prompt text uses — when the two disagreed, a
        # shot whose action was all about one player was anchored to a photo
        # of someone else, and the model drew both.
        #
        # Exactly ONE still per person. Padding a solo shot with a second
        # still of the same face is what taught the model to compose that
        # person twice (two Mbappés in one frame, observed 2026-08-28).
        refs: list[Path] = []
        for member in prompts.visible_cast(plan, scene):
            refs += catalog.select_references(references.get(member.id), scene.camera)[:1]
        if scene.index > 0 and venue_anchor:
            refs = refs[:2] + [venue_anchor[0]]
        best_path, best_hard = None, None

        for attempt in range(1, MAX_KEYFRAME_ATTEMPTS + 1):
            asset.attempts = attempt
            if ledger.exhausted():
                asset.note("budget reached; skipped keyframe generation")
                break
            prompt = base_prompt if best_hard is None else prompts.escalate(
                base_prompt, best_hard
            )
            target = work_dir / f"scene{scene.index}_kf{attempt}.jpg"
            path, cost = images.generate(prompt, target, references=refs)
            ledger.charge(cost)
            asset.cost_usd += cost
            if not path:
                asset.note(f"attempt {attempt}: image generation returned nothing")
                continue

            verdict = review.review_keyframe(path, subject, reviewer)
            asset.review = verdict.to_dict()
            if verdict:
                asset.keyframe_path = str(path)
                for soft in verdict.soft:
                    asset.note(soft)
                break
            asset.note(f"attempt {attempt} rejected: {verdict.reason}")
            if best_hard is None or len(verdict.hard) < len(best_hard):
                best_path, best_hard = path, verdict.hard

        if not asset.keyframe_path and best_path is not None:
            asset.keyframe_path = str(best_path)
            asset.note(f"no attempt passed review; kept the closest ({'; '.join(best_hard)})")
            result.warn(f"scene {scene.index}: shipped a frame that failed review")

        if not asset.keyframe_path:
            try:
                placeholder = media.placeholder_image(
                    work_dir / f"scene{scene.index}_placeholder.jpg", plan.title,
                    size=size,
                )
                asset.keyframe_path = str(placeholder)
                asset.note("used placeholder still")
                result.warn(f"scene {scene.index}: fell back to a placeholder still")
            except media.MediaError:
                asset.note("placeholder generation failed")

        with done_count:
            finished[0] += 1
            say(f"scene {scene.index + 1}: keyframe done "
                f"(${ledger.spent:.2f} spent so far)",
                f"Designed {finished[0]} of {total} scenes")
        return asset

    say(f"designing {total} scenes, up to {MAX_PARALLEL_SCENES} at a time",
        f"Designing {total} scenes")
    # Scene 0 renders first, alone (~12s of extra wall-clock): its keyframe
    # becomes the world-anchor reference for every other scene, which is
    # worth far more than full parallelism ever was.
    assets = [make_keyframe(plan.scenes[0])]
    if assets[0].keyframe_path and "placeholder" not in Path(assets[0].keyframe_path).name:
        venue_anchor.append(Path(assets[0].keyframe_path))
    rest = plan.scenes[1:]
    if rest:
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_SCENES, len(rest))) as pool:
            assets += list(pool.map(make_keyframe, rest))

    # ------------------------------------------------------ 5. animation
    stage(STAGE_ANIMATE)
    video = providers.video_provider(resolution)
    using_stub = isinstance(video, providers.StubVideoProvider)
    if using_stub:
        result.warn("video generation is off; animating keyframes locally")

    animated = [0]

    def animate_scene(pair) -> None:
        """One scene's animation. Independent of every other scene."""
        scene, asset = pair
        if not asset.keyframe_path:
            return
        keyframe = Path(asset.keyframe_path)
        target = work_dir / f"scene{scene.index}.mp4"
        motion = prompts.build_motion_prompt(plan, scene)

        if not ledger.exhausted():
            started = time.time()
            path, cost = video.animate(motion, scene.seconds, target, first_frame=keyframe)
            ledger.charge(cost)
            asset.cost_usd += cost
            with done_count:
                animated[0] += 1
                say(f"scene {scene.index + 1}: "
                    f"{'animated' if path else 'animation failed'} in "
                    f"{time.time() - started:.0f}s (${ledger.spent:.2f} spent so far)",
                    f"Brought {animated[0]} of {total} scenes to life")
        else:
            path = None
            asset.note("budget reached; skipped animation")
            say(f"scene {scene.index + 1}: budget ceiling reached; using a still instead",
                f"Finishing scene {scene.index + 1}")

        if not path and not using_stub:
            # Documented fallback: a still with a slow push-in beats no scene.
            try:
                path = media.ken_burns(keyframe, scene.seconds, target, size=size)
                asset.note("animation failed; used Ken Burns fallback")
                result.warn(f"scene {scene.index}: animation fell back to a still")
            except media.MediaError:
                path = None

        if path:
            asset.clip_path = str(path)
            asset.ok = True
        else:
            asset.note("scene produced no clip")
            result.warn(f"scene {scene.index}: dropped")

    say(f"animating {total} scenes, up to {MAX_PARALLEL_SCENES} at a time — "
        f"the slow stage, ~1-2 min",
        f"Bringing {total} scenes to life")
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_SCENES, total)) as pool:
        # list() forces every future to complete (and re-raises nothing —
        # animate_scene never raises).
        list(pool.map(animate_scene, list(zip(plan.scenes, assets))))

    # The ledger is the only thing that counted spend while workers ran
    # concurrently; copy it back so the DB, result.json and the log agree.
    result.cost_usd = ledger.spent
    result.assets = assets
    usable = [a for a in assets if a.ok and a.clip_path]
    if not usable:
        result.error = "no scene produced a usable clip"
        _write(work_dir / "assets.json", [a.__dict__ for a in assets])
        return result

    # ------------------------------------------------------- 6. assemble
    stage(STAGE_ASSEMBLE)
    scenes_by_index = {s.index: s for s in plan.scenes}
    normalised: list[Path] = []
    captions: list[tuple[float, float, str]] = []
    clock = 0.0
    # Give every clip an audio track first, then ask whether they already agree
    # with one another. They almost always do — same generator, same job, same
    # settings — and when they do the video streams can be copied straight
    # through instead of re-encoded, which is the expensive half of assembly.
    sources: list[tuple[object, Path]] = []
    for asset in usable:
        source = Path(asset.clip_path)
        try:
            if not media.probe(source).get("has_audio"):
                source = media.silent_track(source, source.with_name(source.stem + "_snd.mp4"))
        except media.MediaError as exc:
            asset.note(f"silent track failed: {exc}")
            result.warn(f"scene {asset.index}: dropped during assembly")
            continue
        sources.append((asset, source))

    stream_copy = media.joinable([media.probe(s) for _, s in sources])
    log.info("assembly: %s", "stream-copying clips (already uniform)"
             if stream_copy else "re-encoding clips to a common spec")

    for asset, source in sources:
        try:
            clip = media.normalise(source, source.with_name(source.stem + "_n.mp4"),
                                   stream_copy=stream_copy, size=size)
        except media.MediaError as exc:
            asset.note(f"normalise failed: {exc}")
            result.warn(f"scene {asset.index}: dropped during assembly")
            continue
        normalised.append(clip)
        # Caption windows come from the *delivered* clip's real duration, not
        # the planned one — generated clips routinely run long or short.
        length = float(media.probe(clip).get("duration") or 0.0)
        scene = scenes_by_index.get(asset.index)
        line = scene.trimmed_line() if scene else ""
        if line and length > 0.5:
            captions.append((clock + 0.15, clock + length - 0.15, line))
        clock += length

    if not normalised:
        result.error = "every scene failed to normalise"
        return result

    say(f"joining {len(normalised)} clips, matching loudness, "
        f"burning {len(captions)} captions and the disclosure",
        "Cutting it together and adding captions")
    try:
        joined = media.concat(normalised, work_dir / "joined.mp4", work_dir)
    except media.MediaError as exc:
        result.error = f"could not join scenes: {exc}"
        return result

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        media.brand(joined, out_path, plan.disclosure, watermark, captions=captions)
    except media.MediaError as exc:
        # Branding is cosmetic; ship the unbranded cut rather than nothing.
        result.warn(f"branding failed ({exc}); delivering unbranded")
        shutil.copyfile(joined, out_path)

    # The outro card is cosmetic too: on any failure the video ships without.
    try:
        carded = media.end_card(out_path, work_dir / "with_outro.mp4", work_dir)
        shutil.copyfile(carded, out_path)
    except media.MediaError as exc:
        result.warn(f"end card failed ({exc}); delivering without outro")

    # ------------------------------------------------------- 7. validate
    stage(STAGE_VALIDATE)
    info = media.probe(out_path)
    result.duration = round(float(info.get("duration") or 0.0), 1)
    if not info:
        result.error = "final file is unreadable"
        return result
    if result.duration <= 0:
        result.error = "final file has no duration"
        return result
    if (info.get("width"), info.get("height")) != size:
        result.warn(f"unexpected dimensions {info.get('width')}x{info.get('height')} "
                    f"(wanted {size[0]}x{size[1]} for {resolution})")
    if not info.get("has_audio"):
        result.warn("final file has no audio track")

    poster = media.poster(out_path, work_dir / "poster.jpg", at=min(1.0, result.duration / 2))
    result.poster_path = poster
    result.video_path = out_path
    result.ok = True

    _write(work_dir / "assets.json", [a.__dict__ for a in assets])
    _write(work_dir / "result.json", {
        "ok": result.ok, "duration": result.duration, "cost_usd": round(result.cost_usd, 4),
        "warnings": result.warnings, "plan_source": plan.source,
        "focus": resolved.focus.to_dict(),
        "scenes": len(plan.scenes), "delivered_scenes": len(normalised),
        "captions": len(captions),
    })
    return result


def _write(path: Path, payload: object) -> None:
    try:
        path.write_text(json.dumps(payload, indent=2, default=str))
    except Exception:  # noqa: BLE001 — artifacts are diagnostics, never load-bearing
        log.exception("could not write %s", path)


# ------------------------------------------------------ storage + provenance

def _provenance(result: Result) -> dict:
    """How this clip was made — small enough for a column, big enough to debug.

    Kept in Postgres rather than as files because the questions worth asking
    are queries ("which takes retry most", "what did scene 3 cost"), and
    because the working files expire while this does not.
    """
    plan = result.plan
    return {
        "plan_source": getattr(plan, "source", "unknown"),
        "title": getattr(plan, "title", ""),
        "focus": getattr(plan, "focus", "generic"),
        "teams": list(getattr(plan, "team_ids", []) or []),
        "cast": [m.id for m in getattr(plan, "cast", [])],
        "style": getattr(plan, "style", ""),
        "warnings": result.warnings,
        "cost_usd": round(result.cost_usd, 4),
        "models": {
            "plan": getattr(settings, "OPENAI_PLAN_MODEL", ""),
            "review": getattr(settings, "OPENAI_REVIEW_MODEL", ""),
            "image": getattr(settings, "IMAGE_MODEL", ""),
            "video": getattr(settings, "VIDEO_MODEL", ""),
            "resolution": result.resolution or getattr(settings, "VIDEO_RESOLUTION", ""),
        },
        "scenes": [
            {
                "index": a.index,
                "attempts": a.attempts,
                "cost_usd": round(a.cost_usd, 4),
                "hard": (a.review or {}).get("hard", []),
                "soft": (a.review or {}).get("soft", []),
                "notes": a.notes,
            }
            for a in result.assets
        ],
    }


def _store_artifacts(clip, work: Path, result: Result) -> dict:
    """Upload what is worth keeping. Never raises — a storage failure must not
    turn a finished video into a failed job.

    If the video upload itself fails even after storage-level retries, the
    finished MP4 is copied into MEDIA_DIR and served from this host instead:
    the user must always end up with a playable video (a `ready` clip with no
    URL renders as a phantom failure in the UI — observed 2026-08-14)."""
    from ..services import storage

    out: dict = {}
    store = None
    try:
        store = storage.get()
        prefix = storage.clip_prefix(clip.user_id, clip.id)

        if result.video_path and Path(result.video_path).exists():
            obj = store.put(f"{prefix}/final.mp4", Path(result.video_path), "video/mp4")
            out["video_key"], out["video_url"] = obj.key, obj.url
        if result.poster_path and Path(result.poster_path).exists():
            obj = store.put(f"{prefix}/poster.jpg", Path(result.poster_path), "image/jpeg")
            out["poster_key"] = obj.key

        # The keyframe that survived review, per scene: the cheapest useful
        # evidence for "why does this scene look like that", and the starting
        # point if we ever re-animate a single scene.
        for asset in result.assets:
            if asset.ok and asset.keyframe_path and Path(asset.keyframe_path).exists():
                store.put(
                    f"{prefix}/scene{asset.index}_keyframe.jpg",
                    Path(asset.keyframe_path), "image/jpeg",
                )
    except Exception:  # noqa: BLE001 — the video is already made
        log.exception("storing artifacts failed for clip %s", clip.id)

    if not out.get("video_url") and result.video_path and Path(result.video_path).exists():
        try:
            local = Path(settings.MEDIA_DIR) / f"{clip.id}.mp4"
            shutil.copyfile(result.video_path, local)
            out["video_url"] = f"{settings.API_BASE_URL}/media/{clip.id}.mp4"
            log.error(
                "clip %s: object storage unavailable — serving video from this "
                "host (%s); re-upload it once storage recovers", clip.id, local
            )
        except Exception:  # noqa: BLE001
            log.exception("local fallback failed for clip %s — clip will have no video URL", clip.id)
    return out


# --------------------------------------------------------------- DB wrapper

def _write_script(db, clip) -> None:
    """Phase 1 of the approval flow: research context, write the detailed
    script (every shot, every dialogue line), store it on the clip, and park
    at `script_ready` for the user's approval. Spends only text pennies."""
    from . import context as context_mod

    clip.status = "planning_story"
    clip.stage_index = 0
    clip.current_step = "Researching the real storyline"
    db.commit()

    resolved = defaults.resolve(
        clip.take, clip.sport, clip.tone, clip.duration_target,
        # What the user asked for beyond the take: other sports the story may
        # cross into, and any teams or players they named.
        also_sports=list(clip.sports or []), subjects=list(clip.subjects or []),
    )
    pack = context_mod.get_pack(resolved.take, resolved.sport)
    clip.current_step = "Writing your script"
    db.commit()

    rejected_note = ""
    history = clip.script_history or []
    if history:
        last = history[-1] if isinstance(history[-1], dict) else {}
        prev_title = str((last.get("script") or {}).get("title") or "")
        feedback = str(last.get("feedback") or "")
        rejected_note = f'Previous script title: "{prev_title}".'
        if feedback:
            rejected_note += f' The user said: "{feedback}".'

    plan = planner.build_plan(
        resolved, providers.text_client(),
        storyline=context_mod.summarize(pack), rejected_note=rejected_note,
    )
    script = plan.to_dict()
    if pack:
        # Kept with the script so "Show script" can show what it was built on.
        script["_context"] = pack
    clip.script = script
    clip.status = "script_ready"
    clip.current_step = None
    db.commit()
    log.info("clip %s: script ready (\"%s\", %d shots, context=%s)",
             clip.id, plan.title, len(plan.scenes), bool(pack))


def _job_budget(db) -> float:
    """Per-job cost ceiling — the DB-backed runtime setting wins over env."""
    try:
        from ..services import runtime_settings

        return runtime_settings.job_cap(db)
    except Exception:  # noqa: BLE001 — a settings problem must not kill a job
        return float(getattr(settings, "MAX_JOB_COST_USD", 8.0))


def _release_credits(db, clip) -> None:
    """A failed clip is free (PRICING rule 3). Idempotent and non-fatal."""
    try:
        from ..services import credits

        credits.refund_video(db, clip)
    except Exception:  # noqa: BLE001 — a refund hiccup must not mask the failure
        log.exception("credit refund failed for clip %s", clip.id)


def run_clip_job(clip_id: uuid.UUID) -> None:
    """Drive one Clip row through the pipeline. Never raises."""
    from ..db import SessionLocal
    from ..models import Clip, GENERATION_STAGES
    from ..services import spend

    db = SessionLocal()
    started = time.time()
    try:
        clip = db.get(Clip, clip_id)
        if clip is None:
            return

        # ---- Phase 1: script (approval flow) --------------------------
        approval_on = str(getattr(settings, "SCRIPT_APPROVAL", "on")).lower() == "on"
        if approval_on and not clip.is_simulated and not clip.script_approved:
            _write_script(db, clip)
            return

        # ---- Phase 2: render ------------------------------------------
        # The daily spend gate applies to RENDERING only — writing a script
        # costs pennies and must never be refused by the video budget.
        may_spend, so_far, limit = spend.allowed(db)
        if not may_spend:
            log.error("daily spend ceiling reached ($%.2f of $%.2f); refusing clip %s",
                      so_far, limit, clip_id)
            clip.status = "failed"
            clip.error = spend.OVER_BUDGET_MESSAGE
            clip.current_step = None
            db.commit()
            _release_credits(db, clip)
            return

        approved_plan = None
        if clip.script and clip.script_approved:
            try:
                approved_plan = VideoPlan.from_dict(clip.script)
            except Exception:  # noqa: BLE001 — a broken stored script re-plans
                log.exception("stored script unreadable for %s; re-planning", clip_id)

        def on_stage(name: str) -> None:
            clip.status = name
            if name in GENERATION_STAGES:
                clip.stage_index = GENERATION_STAGES.index(name)
            db.commit()

        def on_progress(detail: str, public: str) -> None:
            # Only the public register reaches the product; `detail` stays in
            # the log, where costs and retry counts belong. Written to the row
            # because the API runs several workers and a poll may land on one
            # that is not running this job.
            clip.current_step = public
            db.commit()

        work = Path(settings.MEDIA_DIR).parent / "work" / str(clip_id)
        out = work / "final.mp4"
        result = generate_video(
            clip.take, clip.sport, clip.tone, clip.duration_target,
            work_dir=work, out_path=out,
            watermark="BanterClips" if clip.watermarked else None,
            on_stage=on_stage,
            on_progress=on_progress,
            resolution=getattr(clip, "resolution", None),
            plan=approved_plan,
            budget=_job_budget(db),
        )

        clip.cost_usd = round(result.cost_usd, 3)
        clip.provenance = _provenance(result)
        # Every video keeps its script ("Show script"), whether or not the
        # approval flow wrote one first.
        if clip.script is None and result.plan is not None:
            clip.script = result.plan.to_dict()

        if result.ok:
            stored = _store_artifacts(clip, work, result)
            clip.status = "ready"
            clip.error = None
            clip.duration_seconds = result.duration
            clip.video_key = stored.get("video_key")
            clip.poster_key = stored.get("poster_key")
            clip.video_url = stored.get("video_url") or clip.video_url
            from datetime import datetime, timezone
            clip.completed_at = datetime.now(timezone.utc)
            clip.current_step = None
        else:
            clip.status = "failed"
            clip.error = (result.error or "generation failed")[:500]
            clip.current_step = None
        db.commit()
        if not result.ok:
            _release_credits(db, clip)
        log.info("clip %s finished in %.1fs ok=%s cost=$%.3f warnings=%d",
                 clip_id, time.time() - started, result.ok, result.cost_usd,
                 len(result.warnings))
    except Exception as exc:  # noqa: BLE001 — job boundary
        log.exception("clip %s crashed", clip_id)
        try:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "failed"
                clip.error = str(exc)[:500]
                db.commit()
                _release_credits(db, clip)
        except Exception:  # noqa: BLE001
            log.exception("could not record failure for %s", clip_id)
    finally:
        db.close()
