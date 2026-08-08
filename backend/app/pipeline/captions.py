"""Generate TikTok-style word-pop ASS captions from word timestamps.

Style matches the BanterClips prototype: white bold words on black chip boxes,
current word highlighted green, group pops in with overshoot and a slight tilt.
"""

from pathlib import Path

from .. import config

MAX_WORDS_PER_GROUP = 3
MAX_CHARS_PER_GROUP = 15  # incl. spaces — keeps fontsize-96 text inside 1080px

def _ass_color(hex_color: str) -> str:
    """#RRGGBB -> ASS &H00BBGGRR."""
    r, g, b = hex_color.lstrip("#")[0:2], hex_color.lstrip("#")[2:4], hex_color.lstrip("#")[4:6]
    return f"&H00{b}{g}{r}".upper()


# BorderStyle=3 => OutlineColour is the opaque box fill (the black chip).
ASS_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.WIDTH}
PlayResY: {config.HEIGHT}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,DejaVu Sans,96,{{accent}},&H00FFFFFF,&H140A0A0C,&H00000000,-1,0,0,0,100,100,0,0,3,20,0,5,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(word: str) -> str:
    return word.strip().strip(",;:").replace("\\", "").replace("{", "(").replace("}", ")")


def _group(words: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    cur: list[dict] = []
    cur_len = 0
    for w in words:
        wlen = len(w["word"])
        if cur and (len(cur) >= MAX_WORDS_PER_GROUP or cur_len + 1 + wlen > MAX_CHARS_PER_GROUP):
            groups.append(cur)
            cur, cur_len = [], 0
        cur.append(w)
        cur_len += wlen + (1 if cur_len else 0)
    if cur:
        groups.append(cur)
    return groups


def _srt_ts(seconds: float) -> str:
    ms = round(max(0.0, seconds) * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: list[dict], out_path: Path) -> None:
    """Plain-text captions (same groups as on screen) in standard SRT."""
    words = [{**w, "word": _clean(w["word"])} for w in words if _clean(w["word"])]
    blocks = []
    for i, group in enumerate(_group(words), start=1):
        text = " ".join(w["word"] for w in group)
        blocks.append(
            f"{i}\n{_srt_ts(group[0]['start'])} --> {_srt_ts(group[-1]['end'])}\n{text}\n"
        )
    out_path.write_text("\n".join(blocks), encoding="utf-8")


def build_ass(words: list[dict], out_path: Path, accent: str = "#32E77B") -> float:
    """Write the ASS file; return total caption duration in seconds."""
    words = [{**w, "word": _clean(w["word"])} for w in words if _clean(w["word"])]
    groups = _group(words)
    lines = [ASS_HEADER.replace("{accent}", _ass_color(accent))]
    for gi, group in enumerate(groups):
        start = group[0]["start"]
        # Hold each group on screen until the next group starts (no gaps/flicker).
        end = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else group[-1]["end"] + 0.4

        # Pop-in with overshoot, alternating slight tilt for energy.
        tilt = 2.2 if gi % 2 == 0 else -2.2
        intro = (
            f"{{\\frz{tilt}\\fscx55\\fscy55"
            f"\\t(0,90,\\fscx110\\fscy110)\\t(90,170,\\fscx100\\fscy100)}}"
        )
        # Karaoke: each word flips from white (secondary) to green (primary)
        # as it is spoken. Durations are centiseconds; gaps attach to the word before.
        parts = [intro]
        for wi, w in enumerate(group):
            w_end = group[wi + 1]["start"] if wi + 1 < len(group) else w["end"]
            dur_cs = max(1, round((w_end - w["start"]) * 100))
            parts.append(f"{{\\k{dur_cs}}}{w['word']} ")
        text = "".join(parts).rstrip()
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Pop,,0,0,0,,{text}\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    return groups[-1][-1]["end"]
