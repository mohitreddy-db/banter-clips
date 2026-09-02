"""FFmpeg helpers. Deterministic; no model ever touches these.

Every function returns a path on success and raises MediaError on failure, so
the runner can decide per scene whether to substitute rather than abort.
"""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("banter.video.media")

# Deliver at the generator's own resolution. Grok returns 720x1280 at "720p",
# so the old 1080x1920 target meant every clip was upscaled to 2.25x the pixels
# before encoding — 2.25x the x264 work for detail that does not exist in the
# source. Measured on the droplet: 4.9s -> 3.0s per clip. Instagram accepts
# 720x1280 Reels natively, so nothing is lost downstream.
#
# Set VIDEO_WIDTH=1080 to go back to upscaling, e.g. if the generator starts
# returning true 1080p. All burn-in geometry below scales with it.
WIDTH = int(os.environ.get("VIDEO_WIDTH", "720"))
HEIGHT = WIDTH * 16 // 9
FPS = 30

# Text sizes and insets are designed against a 1080-wide frame and scaled as
# fractions per call, so captions land in the same place at any delivery width.


# What the generator actually delivers per resolution tier. Grok's "1080p" is
# 1088x1920 (measured on every 1080p job — 1088 = 17×64, a model block-size
# artefact). Targeting 1080 exactly would force a re-encode of every scene
# that the stream-copy fast path otherwise avoids, for 8 invisible pixels.
_TIER_DIMS = {"720p": (720, 1280), "1080p": (1088, 1920)}


def dims(resolution: str | None) -> tuple[int, int]:
    """Frame size for a per-clip resolution ("720p"/"1080p").

    Resolution became a per-clip choice (Creator picks 1080p), so the module
    constants above are only the default; anything unrecognised falls back to
    them. Height is forced even — x264 rejects odd dimensions.
    """
    known = _TIER_DIMS.get(str(resolution or "").lower())
    if known:
        return known
    try:
        width = int(str(resolution or "").lower().removesuffix("p"))
    except ValueError:
        return WIDTH, HEIGHT
    if width < 240 or width > 2160:
        return WIDTH, HEIGHT
    return width, (width * 16 // 9) // 2 * 2

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


def fit_frame(src: str | Path, out: Path, width: int = 720, height: int = 1280) -> Path | None:
    """Cover-crop a frame to exactly width x height, centred.

    Chat-based image models (the identity route) return whatever aspect they
    like; the animation stage expects the keyframe to match the video's 9:16
    canvas, and a mismatched first frame gets stretched or letterboxed."""
    try:
        _run(["ffmpeg", "-y", "-i", str(src), "-vf",
              f"scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height}", "-frames:v", "1", "-q:v", "2", str(out)],
             "frame fit")
    except MediaError:
        log.exception("could not fit frame %s", src)
        return None
    return out if out.exists() else None


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
        "sample_rate": int((audio or {}).get("sample_rate") or 0),
        "channels": int((audio or {}).get("channels") or 0),
        "has_audio": audio is not None,
        "fps": _ratio(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        # ffprobe omits this entirely when the pixels are already square.
        "sar": video.get("sample_aspect_ratio") or "1:1",
    }


def _ratio(value: str | None) -> float:
    """ffprobe reports frame rates as "30/1". Returns 0.0 when unparseable."""
    try:
        num, _, den = str(value or "").partition("/")
        return round(float(num) / float(den or 1), 3)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def ken_burns(image: str | Path, seconds: float, out: str | Path,
              size: tuple[int, int] | None = None) -> Path:
    """Animate a still with a slow push-in, plus a silent audio track.

    This is the documented fallback when a scene cannot be animated — and it
    is also what the pipeline uses while video generation is switched off, so
    a job always yields something watchable.
    """
    width, height = size or (WIDTH, HEIGHT)
    seconds = max(1.0, float(seconds))
    frames = int(seconds * FPS)
    # zoompan works on an upscaled source to avoid visible stepping.
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='min(zoom+0.0009,1.12)':d={frames}:s={width}x{height}:fps={FPS},"
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


def joinable(infos: list[dict]) -> bool:
    """True when these clips already share one video spec, so concat can join
    them without a single frame being re-encoded.

    The test is whether the clips agree with *each other*, not whether they hit
    the WIDTH/HEIGHT/FPS constants. That matters: the generator returns
    720x1280 at 24fps, so a target pinned to 30fps would re-encode every clip
    forever while the clips were already perfectly compatible. Portrait shape
    is still required, since a landscape source genuinely needs the crop.
    """
    if not infos or not all(infos):
        return False
    specs = {(i.get("width"), i.get("height"), i.get("vcodec"), i.get("fps"),
              i.get("sar")) for i in infos}
    if len(specs) != 1:
        return False
    (width, height, vcodec, fps, _sar), = specs
    return bool(
        width and height
        and vcodec == "h264"
        and fps
        and height > width                      # already portrait
        and all(i.get("has_audio") for i in infos)
    )


def normalise(clip: str | Path, out: str | Path, trim: tuple[float, float] | None = None,
              stream_copy: bool = False, size: tuple[int, int] | None = None) -> Path:
    """Common resolution, fps and loudness so clips can be joined seamlessly.

    With `stream_copy` the caller has already established (via `joinable`) that
    every clip shares one spec, so re-encoding the video is pure waste — it
    re-compresses identical pixels for nothing. Copy the video stream and
    re-encode only the audio, which still leaves scenes loudness-matched (the
    one thing concat cannot fix afterwards) for a fraction of the CPU.

    The fast path is deliberately conservative: any trim, any missing audio, or
    any failure falls through to the full re-encode below.
    """
    if stream_copy and trim is None and probe(clip).get("has_audio"):
        try:
            _run([
                "ffmpeg", "-v", "error", "-y", "-i", str(clip),
                "-c:v", "copy", "-af", LOUDNESS,
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out),
            ], "normalise (stream copy)")
            log.info("normalise: stream-copied %s", clip)
            return Path(out)
        except MediaError as exc:
            log.warning("stream-copy normalise failed (%s); re-encoding", exc)

    width, height = size or (WIDTH, HEIGHT)
    args = ["ffmpeg", "-v", "error", "-y"]
    if trim:
        args += ["-ss", f"{trim[0]:.2f}", "-to", f"{trim[1]:.2f}"]
    args += [
        "-i", str(clip),
        "-vf", (f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={width}:{height},fps={FPS},setsar=1"),
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


CAPTION_WRAP_CHARS = 24
CAPTION_MAX_LINES = 2
# Captions are burned as short timed word-groups ("karaoke" style), not one
# static block. The block style truncated: 2 lines × 24 chars dropped the
# rest of the sentence SILENTLY, and every clip reviewed on 2026-08-20 shipped
# with a punchline cut mid-word. Chunking also matches how real sports reels
# caption speech.
CAPTION_CHUNK_CHARS = 18
CAPTION_MIN_CHUNK_SECONDS = 0.6


def _caption_geometry(size: tuple[int, int]) -> tuple[int, int]:
    """(font size, base y) for a frame. The base line sits low in the frame,
    over the ground plane rather than over people's knees, and still clear of
    the Instagram UI chrome along the bottom (~13% of the frame). The old
    fixed value (73% down) sat right where a standing figure's legs are and
    left a fifth of the frame unused beneath it."""
    width, height = size
    s = width / 1080.0
    return round(46 * s), height - round(360 * s)


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


def caption_chunks(text: str, seconds: float) -> list[tuple[float, float, str]]:
    """Split one spoken line into timed word-groups covering [0, seconds).

    Every word survives — a chunk that would flash by too fast is merged into
    wider chunks instead of dropped. Each chunk's window is proportional to
    its word count, approximating speech pacing without a transcript.
    """
    words = str(text or "").split()
    if not words or seconds <= 0:
        return []
    def paced_ok(parts: list[str]) -> bool:
        total = sum(len(p.split()) for p in parts)
        return all(
            seconds * len(p.split()) / total >= CAPTION_MIN_CHUNK_SECONDS
            for p in parts
        )

    width = CAPTION_CHUNK_CHARS
    chunks = _wrap(" ".join(words), width)
    while len(chunks) > 1 and not paced_ok(chunks):
        width = int(width * 1.5)
        chunks = _wrap(" ".join(words), width)
    total_words = sum(len(c.split()) for c in chunks)
    out, clock = [], 0.0
    for chunk in chunks:
        dur = seconds * len(chunk.split()) / total_words
        out.append((clock, min(seconds, clock + dur), chunk))
        clock += dur
    return out


def caption_filters(
    captions: list[tuple[float, float, str]], font: str, scratch: Path | None = None,
    size: tuple[int, int] | None = None,
) -> list[str]:
    """drawtext filters for timed captions.

    Each caption is (start, end, text): one scene's spoken line over its
    window. The line is burned as a sequence of short timed word-groups —
    never as a truncated block (see CAPTION_CHUNK_CHARS). Every group becomes
    its own drawtext, because newlines inside one drawtext render literally
    as "n" (measured).
    """
    width, height = size or (WIDTH, HEIGHT)
    font_size, base_y = _caption_geometry((width, height))
    s = width / 1080.0
    scratch = Path(scratch) if scratch else Path(tempfile.mkdtemp(prefix="banter_text_"))
    scratch.mkdir(parents=True, exist_ok=True)
    filters = []
    for index, (start, end, text) in enumerate(captions):
        for part, (t0, t1, chunk) in enumerate(caption_chunks(text, max(0.0, end - start))):
            lines = _wrap(chunk, CAPTION_WRAP_CHARS)[:CAPTION_MAX_LINES]
            for row, line in enumerate(lines):
                y = base_y + row * int(font_size * 1.3)
                source = _text_source(line, scratch, f"cap{index}_{part}_{row}")
                filters.append(
                    f"drawtext=fontfile={font}:{source}:fontcolor=white"
                    f":fontsize={font_size}:borderw={max(2, round(4 * s))}"
                    f":bordercolor=black@0.85"
                    f":x=(w-text_w)/2:y={y}"
                    f":enable='between(t,{start + t0:.2f},{start + t1:.2f})'"
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

    Text geometry follows the *input video's* actual frame, probed here —
    resolution is a per-clip choice now, so a fixed scale factor would draw
    720p-sized text on a 1080p frame.
    """
    info = probe(video)
    size = (info.get("width") or WIDTH, info.get("height") or HEIGHT)
    s = size[0] / 1080.0
    font = font_path()
    filters = []
    scratch = Path(tempfile.mkdtemp(prefix="banter_text_"))
    if font:
        if captions:
            filters.extend(caption_filters(captions, font, scratch, size=size))
        if disclosure:
            source = _text_source(disclosure, scratch, "disclosure")
            filters.append(
                f"drawtext=fontfile={font}:{source}:fontcolor=white@0.82"
                f":fontsize={round(32 * s)}:borderw={max(2, round(3 * s))}"
                f":bordercolor=black@0.75:x=(w-text_w)/2:y={round(95 * s)}"
            )
        if watermark:
            source = _text_source(watermark, scratch, "watermark")
            filters.append(
                f"drawtext=fontfile={font}:{source}:fontcolor=white@0.88"
                f":fontsize={round(38 * s)}:borderw={max(2, round(3 * s))}"
                f":bordercolor=black@0.75:x=w-text_w-{round(48 * s)}:y=h-{round(160 * s)}"
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


# The outro card: "made with <logo> BanterClips" over a short synthesized
# sting, holding ~2s — the TikTok-outro pattern with our own art and sound.
# One of four styles is picked at random per video so the ending never gets
# stale; pin one with END_CARD_STYLE (also how a style is retired quickly).
# The main video is never re-encoded: the "smooth transition" is a
# freeze-frame dissolve baked into the card itself — its first beats
# crossfade FROM the video's final frame — so the splice stays a stream copy.
END_CARD_SECONDS = float(os.environ.get("END_CARD_SECONDS", "2.0"))
END_CARD_XFADE = 0.4
END_CARD_STYLES = ("navy", "gradient", "stamp", "light")
_END_CARD_LOGO = Path(__file__).parent / "assets" / "logo.png"

# Synthesized stings (aevalsrc expressions) — struck notes with exponential
# decay, nothing sampled. Onsets sit just after the dissolve (t≈0.45) so the
# sound lands with the text, not under the previous scene's tail.
_STING = {
    # rising three-note "ta-da-da" (C5-G5-C6)
    "navy": ("0.35*(gte(t,0.45)*sin(2*PI*523.25*t)*exp(-7*(t-0.45))"
             "+gte(t,0.61)*sin(2*PI*783.99*t)*exp(-7*(t-0.61))"
             "+gte(t,0.79)*sin(2*PI*1046.5*t)*exp(-5.5*(t-0.79)))"),
    # faster four-note sparkle (C5-E5-G5-C6)
    "gradient": ("0.32*(gte(t,0.45)*sin(2*PI*523.25*t)*exp(-8*(t-0.45))"
                 "+gte(t,0.57)*sin(2*PI*659.26*t)*exp(-8*(t-0.57))"
                 "+gte(t,0.69)*sin(2*PI*783.99*t)*exp(-8*(t-0.69))"
                 "+gte(t,0.81)*sin(2*PI*1046.5*t)*exp(-5*(t-0.81)))"),
    # bass thud + tick when the lockup lands, softer settle hit after
    "stamp": ("0.9*gte(t,0.70)*sin(2*PI*72*t)*exp(-9*(t-0.70))"
              "+0.4*gte(t,0.70)*sin(2*PI*1400*t)*exp(-70*(t-0.70))"
              "+gte(t,1.05)*(0.45*sin(2*PI*95*t)*exp(-11*(t-1.05))"
              "+0.2*sin(2*PI*1800*t)*exp(-80*(t-1.05)))"),
    # one soft marimba-ish ding with overtones
    "light": ("0.30*gte(t,0.50)*(sin(2*PI*880*t)+0.35*sin(2*PI*1760*t)"
              "+0.15*sin(2*PI*2640*t))*exp(-4.5*(t-0.50))"),
}


def _end_texts(s: float, font: str, made: str = "white", mark: str = "white",
               site: str = "0x22D3EE", animate: bool = True) -> list[str]:
    """The card's text lockup: "made with", wordmark, site line — the logo
    mark is overlaid separately. Beats start after the dissolve (t≈0.4);
    `animate=False` renders the settled layout (the stamp style's still)."""
    a1 = ":alpha='0.75*min(1,max(0,(t-0.40)/0.30))'" if animate else ""
    a2 = ":alpha='min(1,max(0,(t-0.45)/0.30))'" if animate else ""
    a3 = ":alpha='min(1,max(0,(t-0.85)/0.30))'" if animate else ""
    wordmark_y = (
        f"'(h-text_h)/2-{round(20 * s)}"
        f"+{round(70 * s)}*pow(1-min(1,max(0,(t-0.45)/0.35)),2)'" if animate
        else f"(h-text_h)/2-{round(20 * s)}"
    )
    return [
        f"drawtext=fontfile={font}:text=made with:fontcolor={made}"
        f":fontsize={round(42 * s)}:x=(w-text_w)/2:y=(h-text_h)/2-{round(380 * s)}{a1}",
        f"drawtext=fontfile={font}:text=BanterClips:fontcolor={mark}"
        f":fontsize={round(104 * s)}:x=(w-text_w)/2:y={wordmark_y}{a2}",
        f"drawtext=fontfile={font}:text=banterclips.com:fontcolor={site}"
        f":fontsize={round(38 * s)}:x=(w-text_w)/2:y=(h-text_h)/2+{round(105 * s)}{a3}",
    ]


def _card_video(style: str, width: int, height: int, fps: float, rate: int,
                channels: int, d: float, work: Path) -> Path:
    """One style's card, sized/paced to the target video, transition not yet
    applied. Every style shares the lockup; they differ in world and sound."""
    font = font_path()
    s = width / 1080.0
    logo_w = round(200 * s)
    logo_y = height // 2 - round(310 * s)
    out = work / f"end_card_{style}.mp4"
    pan = "stereo|c0=c0|c1=c0" if channels == 2 else "mono|c0=c0"
    audio = ["-f", "lavfi", "-i", f"aevalsrc='{_STING[style]}':s={rate}:d={d:.2f}"]
    encode = [
        "-c:v", "libx264", "-preset", PRESET, "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(rate), "-ac", str(channels),
        "-t", f"{d:.2f}", str(out),
    ]
    afilter = ["-af", f"pan={pan},afade=t=out:st={d - 0.35:.2f}:d=0.35"]

    if style == "stamp":
        # The whole lockup (logo included) rendered once at 2x, then slammed
        # in with zoompan: hold oversized through the dissolve, land, settle.
        still = work / "end_card_stamp.png"
        _run(["ffmpeg", "-v", "error", "-y",
              "-f", "lavfi", "-i", f"color=c=0x05070D:s={width * 2}x{height * 2}",
              "-loop", "1", "-i", str(_END_CARD_LOGO),
              "-filter_complex",
              (f"[0:v]{','.join(_end_texts(s * 2, font, animate=False))}[bg];"
               f"[1:v]scale={logo_w * 2}:-1[lg];"
               f"[bg][lg]overlay=(W-w)/2:{logo_y * 2}[outv]"),
              "-map", "[outv]", "-frames:v", "1", str(still)], "end card still")
        lead, slam = round(0.35 * fps), round(0.35 * fps)
        zoom = f"'if(lte(on,{lead}),1.9,if(lte(on,{lead + slam}),1.9-0.9*(on-{lead})/{slam},1))'"
        _run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(still), *audio,
              "-vf", (f"zoompan=z={zoom}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      f":d={int(d * fps)}:s={width}x{height}:fps={fps:g},setsar=1,format=yuv420p"),
              *afilter, *encode], f"end card {style}")
        return out

    if style == "gradient":
        bg = (f"gradients=s={width}x{height}:c0=0x3D2C8D:c1=0x0E7490"
              f":speed=0.03:duration={d:.2f}:rate={fps:g}")
        texts = _end_texts(s, font)
    elif style == "light":
        bg = f"color=c=0xF4F6FB:s={width}x{height}:r={fps:g}:d={d:.2f}"
        texts = _end_texts(s, font, made="0x64748B", mark="0x0B1220", site="0x0891B2")
    else:  # navy
        bg = f"color=c=0x0A1020:s={width}x{height}:r={fps:g}:d={d:.2f}"
        texts = _end_texts(s, font)
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", bg,
          "-loop", "1", "-i", str(_END_CARD_LOGO), *audio,
          "-filter_complex",
          (f"[0:v]{','.join(texts)}[bg];"
           f"[1:v]scale={logo_w}:-1,fade=in:st=0.45:d=0.30:alpha=1[lg];"
           f"[bg][lg]overlay=(W-w)/2:{logo_y}:shortest=1,setsar=1,format=yuv420p[outv]"),
          "-map", "[outv]", "-map", "2:a", *afilter, *encode], f"end card {style}")
    return out


def end_card(video: str | Path, out: str | Path, work: Path,
             style: str | None = None) -> Path:
    """Append the branded outro to a finished video, in a per-video random
    style, dissolving smoothly out of the video's last frame.

    The card is rendered at the video's own measured size, frame rate and
    audio spec with the same codec settings, so the join is a stream copy —
    no re-encode of the paid content. Raises MediaError; callers treat the
    outro as cosmetic (a job never fails because of it).
    """
    info = probe(video)
    width, height = int(info.get("width") or 0), int(info.get("height") or 0)
    fps = float(info.get("fps") or FPS)
    # A stream copy needs the audio specs to agree exactly — a 44.1k source
    # spliced to a 48k card plays the tail at the wrong clock (measured).
    rate = int(info.get("sample_rate") or 48000)
    channels = max(1, int(info.get("channels") or 2))
    if not (width and height and font_path()):
        raise MediaError("end card needs a readable frame and a font")
    if not _END_CARD_LOGO.exists():
        raise MediaError(f"logo asset missing: {_END_CARD_LOGO}")
    style = (style or os.environ.get("END_CARD_STYLE", "")).strip().lower()
    if style not in END_CARD_STYLES:
        style = random.choice(END_CARD_STYLES)
    work = Path(work)
    d = END_CARD_SECONDS

    raw = _card_video(style, width, height, fps, rate, channels, d, work)
    # The transition: the video's final frame crossfades into the card's
    # opening. Re-encodes only the 2s card; the main video is untouched.
    frozen = work / "end_card_frozen.png"
    _run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.15", "-i", str(video),
          "-frames:v", "1", "-update", "1", str(frozen)], "end card frame")
    card = work / "end_card.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-loop", "1", "-t", f"{END_CARD_XFADE + 0.1:.2f}",
          "-framerate", f"{fps:g}", "-i", str(frozen),
          "-i", str(raw),
          "-filter_complex",
          (f"[0:v]scale={width}:{height},setsar=1,fps={fps:g},settb=AVTB[v0];"
           f"[1:v]fps={fps:g},settb=AVTB[v1];"
           f"[v0][v1]xfade=transition=fade:duration={END_CARD_XFADE:.2f}:offset=0,"
           f"format=yuv420p[outv]"),
          "-map", "[outv]", "-map", "1:a",
          "-c:v", "libx264", "-preset", PRESET, "-crf", "20", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-ar", str(rate), "-ac", str(channels),
          "-t", f"{d:.2f}", str(card)], "end card dissolve")

    listing = work / "end_card_concat.txt"
    listing.write_text(f"file '{Path(video).resolve()}'\nfile '{card.resolve()}'\n")
    _run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
          "-i", str(listing), "-c", "copy", "-movflags", "+faststart",
          str(out)], "end_card concat")
    # A bad splice shows up as lost duration; catch it here so the caller
    # can ship the card-less cut instead of a corrupt file.
    want = (info.get("duration") or 0.0) + d
    got = probe(out).get("duration") or 0.0
    if abs(got - want) > 1.0:
        raise MediaError(f"spliced duration {got:.1f}s != expected {want:.1f}s")
    log.info("end card: %s style spliced onto %s", style, video)
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


def placeholder_image(out: str | Path, text: str = "",
                      size: tuple[int, int] | None = None) -> Path:
    """A gradient still, used when even image generation is unavailable."""
    width, height = size or (WIDTH, HEIGHT)
    s = width / 1080.0
    font = font_path()
    vf = "format=yuv420p"
    if font and text:
        vf = (f"drawtext=fontfile={font}:text='{_esc(text[:40])}':fontcolor=white@0.9"
              f":fontsize={round(64 * s)}:x=(w-text_w)/2:y=(h-text_h)/2,{vf}")
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
          "-i", f"gradients=s={width}x{height}:c0=0x3d2c8d:c1=0x7b2ff7:duration=1",
          "-vf", vf, "-frames:v", "1", str(out)], "placeholder_image")
    return Path(out)


def _esc(text: str) -> str:
    for a, b in (("\\", r"\\"), (":", r"\:"), ("'", r"\'"), (",", r"\,"), ("%", r"\%")):
        text = text.replace(a, b)
    return text
