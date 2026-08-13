"""FFmpeg helpers. Deterministic; no model ever touches these.

Every function returns a path on success and raises MediaError on failure, so
the runner can decide per scene whether to substitute rather than abort.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("banter.video.media")

WIDTH, HEIGHT, FPS = 1080, 1920, 30

# x264 preset for every encode. "medium" at 1080x1920 saturates a single core
# for minutes — measured on the droplet as load 12 and an API that stopped
# answering while a clip assembled. "veryfast" is several times cheaper for
# roughly 10-15% more bytes, which is the right trade when the same core also
# has to serve the site. Override with FFMPEG_PRESET on bigger hardware.
PRESET = os.environ.get("FFMPEG_PRESET", "veryfast")
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


class MediaError(RuntimeError):
    pass


def available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def font_path() -> str | None:
    return next((f for f in FONT_CANDIDATES if Path(f).exists()), None)


def _run(args: list[str], what: str) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise MediaError(f"{what} failed: {result.stderr.strip()[-400:]}")


def probe(path: str | Path) -> dict:
    """Duration, dimensions and stream presence. Returns {} if unreadable."""
    args = ["ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path)]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float((data.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "vcodec": video.get("codec_name") or "",
        "acodec": (audio or {}).get("codec_name") or "",
        "has_audio": audio is not None,
    }


def ken_burns(image: str | Path, seconds: float, out: str | Path) -> Path:
    """Animate a still with a slow push-in, plus a silent audio track.

    This is the documented fallback when a scene cannot be animated — and it
    is also what the pipeline uses while video generation is switched off, so
    a job always yields something watchable.
    """
    seconds = max(1.0, float(seconds))
    frames = int(seconds * FPS)
    # zoompan works on an upscaled source to avoid visible stepping.
    vf = (
        f"scale={WIDTH * 2}:{HEIGHT * 2}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH * 2}:{HEIGHT * 2},"
        f"zoompan=z='min(zoom+0.0009,1.12)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"setsar=1,format=yuv420p"
    )
    _run([
        "ffmpeg", "-v", "error", "-y",
        "-loop", "1", "-i", str(image),
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
        "-vf", vf, "-t", f"{seconds:.2f}",
        "-c:v", "libx264", "-preset", PRESET, "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(out),
    ], "ken_burns")
    return Path(out)


def normalise(clip: str | Path, out: str | Path, trim: tuple[float, float] | None = None) -> Path:
    """Common resolution, fps and loudness so clips can be joined seamlessly."""
    args = ["ffmpeg", "-v", "error", "-y"]
    if trim:
        args += ["-ss", f"{trim[0]:.2f}", "-to", f"{trim[1]:.2f}"]
    args += [
        "-i", str(clip),
        "-vf", (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={WIDTH}:{HEIGHT},fps={FPS},setsar=1"),
        "-af", LOUDNESS,
        "-c:v", "libx264", "-preset", PRESET, "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out),
    ]
    _run(args, "normalise")
    return Path(out)


def silent_track(clip: str | Path, out: str | Path) -> Path:
    """Give a video without audio a silent stereo track, so concat stays uniform."""
    _run([
        "ffmpeg", "-v", "error", "-y", "-i", str(clip),
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(out),
    ], "silent_track")
    return Path(out)


def concat(clips: list[Path], out: str | Path, work: Path) -> Path:
    """Join pre-normalised clips without re-encoding."""
    if not clips:
        raise MediaError("nothing to concatenate")
    if len(clips) == 1:
        shutil.copyfile(clips[0], out)
        return Path(out)
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
          "-i", str(listing), "-c", "copy", str(out)], "concat")
    return Path(out)


CAPTION_FONT_SIZE = 46
CAPTION_WRAP_CHARS = 24
CAPTION_MAX_LINES = 2
# Low in the frame, over the ground plane rather than over people's knees, and
# still clear of the ~250px of Instagram UI chrome along the bottom. The old
# value (HEIGHT - 520 = 73% down) sat right where a standing figure's legs are
# and left 400px of unused frame beneath it.
CAPTION_BASE_Y = HEIGHT - 360


def _text_source(text: str, scratch: Path, name: str) -> str:
    """Write drawtext's text to a file and return the `textfile=` argument.

    Caption text is written by a language model, so it can contain quotes,
    colons, commas, percent signs and backslashes — every one of which means
    something inside a filtergraph. Escaping them correctly is possible but
    unforgiving: an ASCII apostrophe once terminated the quoted string early,
    which turned the commas in `enable=between(t,a,b)` into filter separators
    and ffmpeg reported `No such filter: '7.75'`. A file has no escaping rules
    at all, so nothing in the text can break the graph.
    """
    path = scratch / f"{name}.txt"
    path.write_text(text, encoding="utf-8")   # no trailing newline: it renders
    return f"textfile={path}"


def caption_filters(
    captions: list[tuple[float, float, str]], font: str, scratch: Path | None = None,
) -> list[str]:
    """drawtext filters for timed captions.

    Each caption is (start, end, text). Text is wrapped to short centred lines
    and every line becomes its own drawtext — newlines inside one drawtext
    render literally as "n" (measured), so multi-line means multi-filter.
    """
    scratch = Path(scratch) if scratch else Path(tempfile.mkdtemp(prefix="banter_text_"))
    scratch.mkdir(parents=True, exist_ok=True)
    filters = []
    for index, (start, end, text) in enumerate(captions):
        lines = _wrap(text, CAPTION_WRAP_CHARS)[:CAPTION_MAX_LINES]
        for row, line in enumerate(lines):
            y = CAPTION_BASE_Y + row * int(CAPTION_FONT_SIZE * 1.3)
            source = _text_source(line, scratch, f"cap{index}_{row}")
            filters.append(
                f"drawtext=fontfile={font}:{source}:fontcolor=white"
                f":fontsize={CAPTION_FONT_SIZE}:borderw=4:bordercolor=black@0.85"
                f":x=(w-text_w)/2:y={y}"
                f":enable='between(t,{start:.2f},{end:.2f})'"
            )
    return filters


def _wrap(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def brand(video: str | Path, out: str | Path, disclosure: str, watermark: str | None,
          captions: list[tuple[float, float, str]] | None = None) -> Path:
    """Burn captions, the AI/parody disclosure, and the watermark on unpaid plans.

    All product copy is deterministic ffmpeg text — the generator never draws
    words (rule §9.6). Falls back to a plain re-encode when no usable font
    exists, so a missing font degrades the frame rather than failing the job.
    """
    font = font_path()
    filters = []
    scratch = Path(tempfile.mkdtemp(prefix="banter_text_"))
    if font:
        if captions:
            filters.extend(caption_filters(captions, font, scratch))
        if disclosure:
            source = _text_source(disclosure, scratch, "disclosure")
            filters.append(
                f"drawtext=fontfile={font}:{source}:fontcolor=white@0.82"
                f":fontsize=32:borderw=3:bordercolor=black@0.75:x=(w-text_w)/2:y=95"
            )
        if watermark:
            source = _text_source(watermark, scratch, "watermark")
            filters.append(
                f"drawtext=fontfile={font}:{source}:fontcolor=white@0.88"
                f":fontsize=38:borderw=3:bordercolor=black@0.75:x=w-text_w-48:y=h-160"
            )
    else:
        log.warning("no usable font found; skipping burn-in")

    args = ["ffmpeg", "-v", "error", "-y", "-i", str(video)]
    if filters:
        args += ["-vf", ",".join(filters)]
    args += ["-c:v", "libx264", "-preset", PRESET, "-crf", "20", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", "-c:a", "copy", str(out)]
    try:
        _run(args, "brand")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return Path(out)


def poster(video: str | Path, out: str | Path, at: float = 0.5) -> Path | None:
    """Grab a thumbnail. Best-effort — a missing poster never fails a job."""
    try:
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(video),
              "-frames:v", "1", "-q:v", "3", str(out)], "poster")
        return Path(out)
    except MediaError:
        log.warning("poster extraction failed for %s", video)
        return None


def placeholder_image(out: str | Path, text: str = "") -> Path:
    """A plain gradient still, used when even image generation is unavailable."""
    font = font_path()
    vf = "format=yuv420p"
    if font and text:
        vf = (f"drawtext=fontfile={font}:text='{_esc(text[:40])}':fontcolor=white@0.9"
              f":fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2,{vf}")
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
          "-i", f"gradients=s={WIDTH}x{HEIGHT}:c0=0x3d2c8d:c1=0x7b2ff7:duration=1",
          "-vf", vf, "-frames:v", "1", str(out)], "placeholder_image")
    return Path(out)


def _esc(text: str) -> str:
    for a, b in (("\\", r"\\"), (":", r"\:"), ("'", r"\'"), (",", r"\,"), ("%", r"\%")):
        text = text.replace(a, b)
    return text
