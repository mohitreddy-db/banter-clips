"""Composite the final 9:16 MP4 with ffmpeg."""

import json
import subprocess
from pathlib import Path

from .. import config
from . import overlays

# style -> fixed palette override ("auto" uses the AI palette)
TEMPLATES = {
    "stadium": ["#7B2FF7", "#C13584", "#F03A70"],
    "neon": ["#0F1035", "#3D2C8D", "#00A9C0"],
}


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-2000:]}")


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def render(
    audio_path: Path,
    ass_path: Path,
    headline: str,
    emoji: str,
    sport: str,
    style: str,
    colors: list[str] | None,
    work_dir: Path,
    out_path: Path,
    content_type: str = "Hot Take",
    handle: str = "",
) -> float:
    palette = TEMPLATES.get(style) or colors or TEMPLATES["stadium"]
    duration = round(audio_duration(audio_path) + 0.6, 2)

    bg_png = work_dir / "bg.png"
    headline_png = work_dir / "headline.png"
    overlays.make_background_png(palette, bg_png)
    overlays.make_headline_png(headline, headline_png)

    # Skip the floating emoji if the headline already carries it inline.
    show_float = bool(emoji) and emoji not in headline
    emoji_png = work_dir / "emoji.png"
    if show_float:
        overlays.make_emoji_png(emoji, emoji_png)

    font = config.FONT_BOLD
    badge = f"{sport.upper()} · {content_type.upper()}"

    # Slow Ken Burns zoom on the mesh gradient — no rotation, just drift.
    zoom = (
        f"scale={config.WIDTH}:{config.HEIGHT},setsar=1,"
        f"zoompan=z='min(1.10,1+0.00028*on)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={config.WIDTH}x{config.HEIGHT}:fps={config.FPS}"
    )
    background = (
        f"{zoom},noise=alls=5:allf=t,vignette=PI/5,"
        f"drawtext=fontfile={font}:text='{badge}':fontcolor=white:fontsize=42:"
        f"x=64:y=132:box=1:boxcolor=black@0.55:boxborderw=24"
    )
    if handle:
        safe_handle = "".join(c for c in handle if c.isalnum() or c in "._-")
        background += (
            f",drawtext=fontfile={font}:text='@{safe_handle}':fontcolor=white@0.7:"
            f"fontsize=36:x=(w-text_w)/2:y=h-150"
        )
    headline_y = "if(lt(t,0.35), 300-220*pow((0.35-t)/0.35,2), 300)"
    emoji_y = "1230+12*sin(2*PI*(t-0.5)/1.4)"

    cmd = ["ffmpeg", "-y"]
    cmd += ["-loop", "1", "-framerate", str(config.FPS), "-i", str(bg_png)]
    cmd += ["-i", str(audio_path)]
    cmd += ["-loop", "1", "-framerate", str(config.FPS), "-i", str(headline_png)]
    if show_float:
        cmd += ["-loop", "1", "-framerate", str(config.FPS), "-i", str(emoji_png)]

    fade_start = max(0.0, duration - 0.5)
    graph = (
        f"[0:v]{background}[bg];"
        f"[2:v]format=rgba,fade=t=in:st=0.05:d=0.25:alpha=1[hl];"
        f"[bg][hl]overlay=x=(W-w)/2:y='{headline_y}'[v1];"
    )
    if show_float:
        graph += (
            f"[3:v]format=rgba,fade=t=in:st=0.45:d=0.3:alpha=1[em];"
            f"[v1][em]overlay=x=(W-w)/2:y='{emoji_y}'[v2];"
        )
    last = "v2" if show_float else "v1"
    graph += (
        f"[{last}]subtitles={ass_path}[v];"
        f"[1:a]apad,afade=t=out:st={fade_start}:d=0.5[a]"
    )

    cmd += [
        "-filter_complex", graph,
        "-map", "[v]", "-map", "[a]",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run(cmd)
    return duration
