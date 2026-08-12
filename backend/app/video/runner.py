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
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..config import settings
from . import (
    catalog, defaults, enhancer, media, planner, prompts, providers, research, review,
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


@dataclass
class Result:
    ok: bool = False
    video_path: Path | None = None
    poster_path: Path | None = None
    duration: float = 0.0
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
) -> Result:
    """Run the whole pipeline. Never raises.

    `brief` is an already-enhanced brief (see `enhancer.enhance`), carrying a
    sharpened take, a fixed style preset and any choices the user made. Passing
    one skips re-enhancement; omitting it runs the raw inputs as before.
    """
    result = Result()
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
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
    say(f"writing the script — {resolved.sport}, {resolved.tone}, "
        f"{resolved.seconds}s in {resolved.scene_count} scenes",
        "Writing your script")
    plan = planner.build_plan(resolved, text)
    say(f"script ready: \"{plan.title}\" ({plan.source}); "
        f"cast {', '.join(m.name for m in plan.cast)}",
        f"Casting {', '.join(m.name for m in plan.cast[:2])}")
    if brief is not None and brief.style:
        # A fixed preset beats a per-job invented style: it is the same look in
        # every scene, which is what keeps a multi-scene video consistent.
        plan.style = brief.style
    result.plan = plan
    if plan.source != "llm":
        result.warn(f"story plan came from the {plan.source} path")
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
    references: dict[str, catalog.Character | None] = {}
    for member in plan.cast:
        if not member.wardrobe:
            member.wardrobe = "plain team-coloured kit with no lettering or numbers"
        char = catalog.get_character(member.id)
        references[member.id] = char
        if char is None and research.enabled():
            # Off-catalog cast: one web-search call buys a real description
            # before any image money is spent.
            if research.enrich_member(member, plan.sport):
                result.warn(f"cast '{member.id}' enriched via web research")
    _write(work_dir / "cast.json", [
        {**m.__dict__,
         "reference_images": [str(p) for p in catalog.select_references(references.get(m.id))]}
        for m in plan.cast
    ])

    # ------------------------------------------------------ 4. keyframes
    stage(STAGE_SCENES)
    images = providers.image_provider()
    reviewer = providers.review_client()
    reviewer = reviewer if getattr(reviewer, "available", False) else None
    if isinstance(images, providers.StubImageProvider):
        # Placeholder gradients are not photographs and never will be. Judging
        # them wastes a review call and all three attempts on every scene.
        reviewer = None
    assets: list[SceneAsset] = []

    for scene in plan.scenes:
        asset = SceneAsset(index=scene.index)
        base_prompt = prompts.build_image_prompt(plan, scene)
        speaker = plan.speaker_for(scene)
        subject = (speaker or plan.cast[0]).name if plan.cast else "the subject"
        # Reference stills anchor the speaker's identity (§5.7): face for
        # close-ups, full body otherwise. Empty when the catalog has none.
        refs = catalog.select_references(
            references.get(speaker.id) if speaker else None, scene.camera
        )
        best_path, best_hard = None, None

        for attempt in range(1, MAX_KEYFRAME_ATTEMPTS + 1):
            asset.attempts = attempt
            if result.cost_usd >= budget:
                asset.note("budget reached; skipped keyframe generation")
                break
            # Retries carry a correction aimed at what the gate rejected;
            # resending the identical prompt mostly reproduces the defect.
            prompt = base_prompt if best_hard is None else prompts.escalate(
                base_prompt, best_hard
            )
            target = work_dir / f"scene{scene.index}_kf{attempt}.jpg"
            say(f"scene {scene.index + 1}/{len(plan.scenes)}: keyframe attempt "
                f"{attempt}/{MAX_KEYFRAME_ATTEMPTS} for {subject}"
                f"{' with reference stills' if refs else ''}",
                f"Designing scene {scene.index + 1} of {len(plan.scenes)}")
            path, cost = images.generate(prompt, target, references=refs)
            result.cost_usd += cost
            asset.cost_usd += cost
            if not path:
                asset.note(f"attempt {attempt}: image generation returned nothing")
                say(f"scene {scene.index + 1}: image generation returned nothing",
                    f"Retrying scene {scene.index + 1}")
                continue

            verdict = review.review_keyframe(path, subject, reviewer)
            asset.review = verdict.to_dict()
            if verdict:
                asset.keyframe_path = str(path)
                for soft in verdict.soft:
                    asset.note(soft)
                say(f"scene {scene.index + 1}: keyframe approved "
                    f"(${result.cost_usd:.2f} spent so far)",
                    f"Scene {scene.index + 1} looks good")
                break
            asset.note(f"attempt {attempt} rejected: {verdict.reason}")
            say(f"scene {scene.index + 1}: rejected — {verdict.reason}; regenerating",
                f"Polishing scene {scene.index + 1}")
            # Keep the least-bad frame: fewer hard failures wins, so exhausting
            # the budget still ships the closest attempt rather than the last.
            if best_hard is None or len(verdict.hard) < len(best_hard):
                best_path, best_hard = path, verdict.hard

        if not asset.keyframe_path and best_path is not None:
            asset.keyframe_path = str(best_path)
            asset.note(f"no attempt passed review; kept the closest ({'; '.join(best_hard)})")
            result.warn(f"scene {scene.index}: shipped a frame that failed review")

        if not asset.keyframe_path:
            # Still no frame: synthesise one so the scene can still exist.
            try:
                placeholder = media.placeholder_image(
                    work_dir / f"scene{scene.index}_placeholder.jpg", plan.title
                )
                asset.keyframe_path = str(placeholder)
                asset.note("used placeholder still")
                result.warn(f"scene {scene.index}: fell back to a placeholder still")
            except media.MediaError:
                asset.note("placeholder generation failed")
        assets.append(asset)

    # ------------------------------------------------------ 5. animation
    stage(STAGE_ANIMATE)
    video = providers.video_provider()
    using_stub = isinstance(video, providers.StubVideoProvider)
    if using_stub:
        result.warn("video generation is off; animating keyframes locally")

    for scene, asset in zip(plan.scenes, assets):
        if not asset.keyframe_path:
            continue
        keyframe = Path(asset.keyframe_path)
        target = work_dir / f"scene{scene.index}.mp4"
        motion = prompts.build_motion_prompt(plan, scene)

        if result.cost_usd < budget:
            say(f"scene {scene.index + 1}/{len(plan.scenes)}: animating "
                f"{scene.seconds:.0f}s at {getattr(settings, 'VIDEO_RESOLUTION', '720p')}"
                f"{'' if not using_stub else ' (local push-in, free)'}"
                f" — this is the slow one, ~1-2 min",
                f"Bringing scene {scene.index + 1} to life")
            started = time.time()
            path, cost = video.animate(motion, scene.seconds, target, first_frame=keyframe)
            result.cost_usd += cost
            asset.cost_usd += cost
            say(f"scene {scene.index + 1}: {'animated' if path else 'animation failed'}"
                f" in {time.time() - started:.0f}s"
                f" (${result.cost_usd:.2f} spent so far)",
                f"Scene {scene.index + 1} is alive")
        else:
            path = None
            asset.note("budget reached; skipped animation")
            say(f"scene {scene.index + 1}: budget ceiling reached; using a still instead",
                f"Finishing scene {scene.index + 1}")

        if not path and not using_stub:
            # Documented fallback: a still with a slow push-in beats no scene.
            try:
                path = media.ken_burns(keyframe, scene.seconds, target)
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
    for asset in usable:
        source = Path(asset.clip_path)
        try:
            if not media.probe(source).get("has_audio"):
                source = media.silent_track(source, source.with_name(source.stem + "_snd.mp4"))
            clip = media.normalise(source, source.with_name(source.stem + "_n.mp4"))
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
    if (info.get("width"), info.get("height")) != (media.WIDTH, media.HEIGHT):
        result.warn(f"unexpected dimensions {info.get('width')}x{info.get('height')}")
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


# --------------------------------------------------------------- DB wrapper

def run_clip_job(clip_id: uuid.UUID) -> None:
    """Drive one Clip row through the pipeline. Never raises."""
    from ..db import SessionLocal
    from ..models import Clip, GENERATION_STAGES

    from ..services import progress

    db = SessionLocal()
    started = time.time()
    progress.start(clip_id)
    try:
        clip = db.get(Clip, clip_id)
        if clip is None:
            return

        def on_stage(name: str) -> None:
            clip.status = name
            if name in GENERATION_STAGES:
                clip.stage_index = GENERATION_STAGES.index(name)
            db.commit()

        def on_progress(detail: str, public: str) -> None:
            # Only the public register reaches the product. `detail` stays in
            # the log, where costs and retry counts belong.
            kind = "step"
            lowered = detail.lower()
            if "rejected" in lowered or "failed" in lowered:
                kind = "warn"
            elif "approved" in lowered or "animated" in lowered:
                kind = "ok"
            progress.push(clip_id, public, kind)

        work = Path(settings.MEDIA_DIR).parent / "work" / str(clip_id)
        out = Path(settings.MEDIA_DIR) / f"{clip_id}.mp4"
        result = generate_video(
            clip.take, clip.sport, clip.tone, clip.duration_target,
            work_dir=work, out_path=out,
            watermark="BanterClips" if clip.watermarked else None,
            on_stage=on_stage,
            on_progress=on_progress,
        )

        if result.ok:
            clip.status = "ready"
            clip.error = None
            clip.duration_seconds = result.duration
            clip.video_url = f"{settings.API_BASE_URL}/media/{clip_id}.mp4"
            from datetime import datetime, timezone
            clip.completed_at = datetime.now(timezone.utc)
        else:
            clip.status = "failed"
            clip.error = (result.error or "generation failed")[:500]
        db.commit()
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
        except Exception:  # noqa: BLE001
            log.exception("could not record failure for %s", clip_id)
    finally:
        db.close()
