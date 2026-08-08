"""Pillow-rendered assets: mesh-gradient background, headline chips (with
inline color emoji), and the floating emoji."""

import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .. import config

EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
MAX_TEXT_WIDTH = 860  # px budget for a headline line, inside 1080 frame
PAD_X, PAD_Y = 34, 20
LINE_GAP = 16

EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # flags
    "\U0001F300-\U0001FAFF"  # symbols, pictographs, supplemental
    "\U00002600-\U000027BF"  # misc symbols, dingbats
    "\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D"   # variation selector, ZWJ
    "]+"
)


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luma(c: tuple[int, int, int]) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _lerp(a: tuple, b: tuple, t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_background_png(colors: list[str], out_path: Path) -> None:
    """Instagram-story-style background: smooth vertical color flow through the
    palette, plus two soft diagonal glows for depth. Rendered at 1/4 scale."""
    w, h = config.WIDTH // 4, config.HEIGHT // 4
    c0, c1, c2 = [_rgb(c) for c in colors]

    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        color = _lerp(c0, c1, t / 0.55) if t < 0.55 else _lerp(c1, c2, (t - 0.55) / 0.45)
        draw.line([(0, y), (w, y)], fill=color)

    # Soft glows (screen blend) — off-axis so nothing reads as a straight band.
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (fx, fy, fr), color in [((0.85, 0.12, 0.75), c1), ((0.10, 0.80, 0.70), c2)]:
        boost = tuple(min(255, int(c * 0.55 + 40)) for c in color)
        r = int(w * fr)
        gd.ellipse(
            [int(w * fx) - r, int(h * fy) - r, int(w * fx) + r, int(h * fy) + r],
            fill=boost,
        )
    glow = glow.filter(ImageFilter.GaussianBlur(w // 3))
    img = ImageChops.screen(img, glow)

    img = ImageEnhance.Color(img).enhance(1.18)
    img = img.resize((config.WIDTH, config.HEIGHT), Image.BICUBIC)
    img.save(out_path)


def _emoji_img(emoji: str, target_h: int) -> Image.Image:
    # NotoColorEmoji is a bitmap font: render at its native 109px, then rescale.
    font = ImageFont.truetype(EMOJI_FONT, 109)
    canvas = Image.new("RGBA", (160 * max(1, len(emoji)), 220), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).text((20, 40), emoji, font=font, embedded_color=True)
    bbox = canvas.getbbox()
    if bbox is None:
        ImageDraw.Draw(canvas).text((20, 40), "🔥", font=font, embedded_color=True)
        bbox = canvas.getbbox()
    canvas = canvas.crop(bbox)
    scale = target_h / canvas.height
    return canvas.resize(
        (max(1, int(canvas.width * scale)), target_h), Image.LANCZOS
    )


def _tokenize(text: str) -> list[tuple[str, str]]:
    """Split into ("text"|"emoji", chunk) runs."""
    runs, pos = [], 0
    for m in EMOJI_RE.finditer(text):
        if m.start() > pos:
            runs.append(("text", text[pos : m.start()]))
        runs.append(("emoji", m.group()))
        pos = m.end()
    if pos < len(text):
        runs.append(("text", text[pos:]))
    return runs


def _word_width(probe, font: ImageFont.FreeTypeFont, word: str, emoji_w: int) -> int:
    return sum(
        emoji_w * len(EMOJI_RE.findall(chunk)) if kind == "emoji"
        else int(probe.textlength(chunk, font=font))
        for kind, chunk in _tokenize(word)
    )


def make_headline_png(headline: str, out_path: Path) -> None:
    """White bold text (+ inline color emoji), one black chip per line."""
    size = 72
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))

    def layout(sz: int):
        f = ImageFont.truetype(config.FONT_BOLD, sz)
        ew = int(sz * 1.12)
        lines, cur, cur_w = [], [], 0
        for word in headline.split():
            ww = _word_width(probe, f, word, ew)
            space = int(probe.textlength(" ", font=f)) if cur else 0
            if cur and cur_w + space + ww > MAX_TEXT_WIDTH:
                lines.append((cur, cur_w))
                cur, cur_w = [], 0
                space = 0
            cur.append(word)
            cur_w += space + ww
        if cur:
            lines.append((cur, cur_w))
        return f, ew, lines

    font, emoji_w, lines = layout(size)
    while size > 44 and any(w > MAX_TEXT_WIDTH for _, w in lines):
        size -= 4
        font, emoji_w, lines = layout(size)

    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    chip_h = line_h + 2 * PAD_Y
    img_w = max(w for _, w in lines) + 2 * PAD_X
    img_h = len(lines) * chip_h + (len(lines) - 1) * LINE_GAP
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, (words, w) in enumerate(lines):
        x0 = (img_w - w) // 2
        y0 = i * (chip_h + LINE_GAP)
        draw.rounded_rectangle(
            [x0 - PAD_X, y0, x0 + w + PAD_X, y0 + chip_h],
            radius=14,
            fill=(10, 10, 12, 235),
        )
        x = x0
        for wi, word in enumerate(words):
            if wi:
                x += int(probe.textlength(" ", font=font))
            for kind, chunk in _tokenize(word):
                if kind == "emoji":
                    for e in EMOJI_RE.findall(chunk):
                        em = _emoji_img(e, emoji_w)
                        img.paste(em, (x, y0 + PAD_Y + (line_h - emoji_w) // 2), em)
                        x += emoji_w
                else:
                    draw.text((x, y0 + PAD_Y), chunk, font=font, fill=(255, 255, 255, 255))
                    x += int(probe.textlength(chunk, font=font))
    img.save(out_path)


def make_emoji_png(emoji: str, out_path: Path, target: int = 170) -> None:
    _emoji_img(emoji, target).save(out_path)
