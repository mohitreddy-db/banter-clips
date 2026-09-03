#!/usr/bin/env python3
"""Render the BanterClips brand marks that search engines and social cards need.

Google will not show an icon beside a search result unless the favicon lives at
a real, crawlable URL — a `data:` URI does not count — so these have to exist as
files in `public/`, not as inline SVG. Same story for `og:image`: crawlers fetch
it, they do not render the page to invent one.

The selected full lockup lives in `frontend/logos`; small-context assets use
the same lockup's extracted B/play mark so the wordmark never becomes a blur.
The generated background uses the app's CSS accent colors.

    pip install pillow
    python3 scripts/gen-brand-assets.py

Fonts are optional. If Manrope/Space Grotesk are not found, the social card's
supporting copy falls back to a system face.
"""

import os
from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "..", "public")
MASTER = os.path.join(HERE, "..", "logos", "banterclips-logo-sample-4.png")
FONT_DIRS = [
    os.environ.get("BRAND_FONT_DIR", ""),
    os.path.join(HERE, "fonts"),
    "/usr/share/fonts/truetype/ubuntu",
]

BG = (11, 13, 19)  # --bg
TEXT = (242, 244, 250)  # --text
MUTED = (152, 161, 181)  # --muted
ACCENT = (34, 211, 238)  # --accent  #22d3ee
ACCENT2 = (52, 226, 122)  # --accent2 #34e27a

def font(names, size, weight=700):
    """First font in `names` that resolves, at `size`. Variable fonts get an
    explicit weight axis — they default to Light, which reads as broken."""
    for d in FONT_DIRS:
        if not d:
            continue
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                f = ImageFont.truetype(p, size)
                try:
                    f.set_variation_by_axes([weight])
                except Exception:
                    pass  # static font — nothing to set
                return f
    return ImageFont.load_default(size)


def display(size, weight=700):
    return font(["SpaceGrotesk-Bold.ttf", "Ubuntu-B.ttf"], size, weight)


def body(size, weight=600):
    return font(["Manrope-ExtraBold.ttf", "Ubuntu-R.ttf"], size, weight)


def diagonal_gradient(w, h, c1, c2):
    """Fast left-to-right brand gradient."""
    ramp = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), c2), Image.new("RGB", (w, h), c1), ramp)


def _rounded(img):
    """Replace generated black corners with real transparency."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, img.width - 1, img.height - 1], radius=round(img.width * 0.205), fill=255
    )
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def lockup(size):
    """Sample 4 as selected: B/play mark plus the BanterClips wordmark."""
    master = Image.open(MASTER).convert("RGB")
    return _rounded(master).resize((size, size), Image.Resampling.LANCZOS)


def _mark():
    """Extract Sample 4's white B/play mark without its lower wordmark."""
    master = Image.open(MASTER).convert("RGB")
    crop = master.crop((330, 240, 925, 835))
    r, g, b = crop.split()
    whiteness = ImageChops.darker(ImageChops.darker(r, g), b)
    alpha = whiteness.point(lambda value: max(0, min(255, (value - 165) * 3)))
    mark = Image.new("RGBA", crop.size, (255, 255, 255, 0))
    mark.putalpha(alpha)
    return mark.crop(alpha.getbbox())


def icon(size):
    """Small-context Sample 4: its B/play mark without duplicate tiny text."""
    scale = 4
    s = size * scale
    grad = diagonal_gradient(s, s, ACCENT, ACCENT2)
    out = _rounded(grad)
    mark = _mark()
    max_w, max_h = round(s * 0.48), round(s * 0.58)
    ratio = min(max_w / mark.width, max_h / mark.height)
    mark = mark.resize(
        (round(mark.width * ratio), round(mark.height * ratio)), Image.Resampling.LANCZOS
    )
    out.alpha_composite(mark, ((s - mark.width) // 2, (s - mark.height) // 2))
    return out.resize((size, size), Image.Resampling.LANCZOS)


def glow(img, cx, cy, radius, color, strength):
    """Soft radial wash — the hero's background glows, cheaply."""
    w, h = img.size
    layer = Image.new("RGB", (w, h), BG)
    px = layer.load()
    for y in range(max(0, cy - radius), min(h, cy + radius)):
        for x in range(max(0, cx - radius), min(w, cx + radius)):
            d = (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5) / radius
            if d >= 1:
                continue
            t = (1 - d) ** 2 * strength
            px[x, y] = tuple(round(b + (c - b) * t) for b, c in zip(BG, color))
    return Image.blend(img, layer, 1.0)


def og_card():
    """1200x630 link preview. Text is kept clear of the outer 60px so nothing
    is clipped when Twitter/Slack crop the card to their own aspect ratios."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BG)
    img = glow(img, 180, -40, 620, (37, 99, 235), 0.30)
    img = glow(img, 1090, 70, 560, (52, 226, 122), 0.16)
    d = ImageDraw.Draw(img)

    mark = icon(74)
    img.paste(mark, (74, 66), mark)
    d.text((166, 78), "BanterClips", font=display(46), fill=TEXT)

    d.text((74, 214), "Turn any sports opinion", font=display(68), fill=TEXT)
    d.text((74, 296), "into a viral video.", font=display(68), fill=ACCENT)

    d.text(
        (74, 412),
        "AI sports videos with voiceover, animated captions and",
        font=body(28, 500),
        fill=MUTED,
    )
    d.text(
        (74, 452),
        "cinematic scenes — ready for Reels, TikTok and Shorts.",
        font=body(28, 500),
        fill=MUTED,
    )

    # Gradient rule anchors the composition and echoes the CTA colour.
    img.paste(diagonal_gradient(300, 6, ACCENT, ACCENT2), (74, 528))
    d.text((74, 556), "banterclips.com", font=body(26, 700), fill=TEXT)
    return img


def main():
    os.makedirs(PUBLIC, exist_ok=True)
    out = lambda n: os.path.join(PUBLIC, n)

    # 48px is Google's floor for a search-result favicon, and it wants a
    # multiple of 48 — the .ico carries 16/32/48 so browsers and Google are
    # both served by one URL.
    ico = icon(192)
    ico.save(out("favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

    icon(32).save(out("favicon-32x32.png"))
    icon(180).save(out("apple-touch-icon.png"))  # iOS ignores transparency
    icon(192).save(out("icon-192.png"))
    icon(512).save(out("icon-512.png"))
    lockup(120).save(out("oauth-logo-120.png"), optimize=True)
    lockup(512).save(out("logo.png"), optimize=True)  # Organization.logo in JSON-LD
    lockup(1024).save(out("logo1024.png"), optimize=True)
    icon(1024).save(out("logo-mark-1024.png"), optimize=True)

    og_card().save(out("og.png"), optimize=True)

    for n in (
        "favicon.ico favicon-32x32.png apple-touch-icon.png icon-192.png "
        "icon-512.png oauth-logo-120.png logo.png logo1024.png "
        "logo-mark-1024.png og.png"
    ).split():
        print(f"  {n:24} {os.path.getsize(out(n)):>8,} bytes")


if __name__ == "__main__":
    main()
