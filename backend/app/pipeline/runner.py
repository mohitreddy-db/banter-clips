"""Orchestrates one video generation job end to end."""

import logging
import shutil

from .. import config, db
from . import audio, captions, render, script

log = logging.getLogger("banter.pipeline")


def run_job(vid: str) -> None:
    job = db.get_video(vid)
    if job is None:
        return
    work = config.WORK_DIR / vid
    work.mkdir(parents=True, exist_ok=True)
    p = job.get("params") or {}
    try:
        db.update_video(vid, status="processing", step="writing_script")
        s = script.write_script(
            job["take"], job["sport"], job["tone"],
            content_type=p.get("content_type") or "Hot Take",
            seconds=p.get("length_seconds") or config.TARGET_SECONDS,
            notes=p.get("notes") or "",
        )
        # Explicit user overrides beat the AI's art direction (still luma-clamped)
        if p.get("colors"):
            s["colors"] = [script._fix_luma("#" + c.lstrip("#").upper()) for c in p["colors"]]
        if p.get("accent"):
            s["accent"] = "#" + p["accent"].lstrip("#").upper()
        db.update_video(vid, script=s, step="voicing")

        voice_path = work / "voice.mp3"
        audio.synthesize(s["script"], job["voice"], voice_path)

        db.update_video(vid, step="timing_captions")
        words = audio.word_timestamps(voice_path)
        ass_path = work / "captions.ass"
        captions.build_ass(words, ass_path, accent=s.get("accent", "#32E77B"))
        srt_path = config.MEDIA_DIR / f"{vid}.srt"
        captions.build_srt(words, srt_path)
        db.update_video(
            vid, captions=words, captions_path=f"/media/{vid}.srt"
        )

        db.update_video(vid, step="rendering")
        out_path = config.MEDIA_DIR / f"{vid}.mp4"
        duration = render.render(
            voice_path, ass_path, s["headline"], s.get("emoji", "🔥"),
            job["sport"], job["style"], s.get("colors"), work, out_path,
            content_type=p.get("content_type") or "Hot Take",
            handle=p.get("handle") or "",
        )

        db.update_video(
            vid,
            status="done",
            step="done",
            video_path=f"/media/{vid}.mp4",
            duration_s=duration,
        )
        shutil.rmtree(work, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001 — job boundary: any failure marks the job failed
        log.exception("job %s failed", vid)
        db.update_video(vid, status="failed", step="failed", error=str(exc)[:500])
