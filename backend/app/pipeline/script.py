"""Turn a raw sports take into a short punchy voiceover script."""

import json
import re

from openai import OpenAI

from .. import config

SYSTEM_PROMPT = """\
You write voiceover scripts for viral 9:16 short-form sports videos (TikTok/Reels/Shorts).
The creator gives you a raw sports opinion. You turn it into a spoken script shaped
by the requested content type (Hot Take = confrontational claim; Prediction =
confident future call; Debate = pick a side and argue it; Reaction = respond to
the news; Roast = mock the target; Analysis = sharp reasoned breakdown).

Rules:
- {min_words} to {max_words} words total. It must be speakable in about {seconds} seconds at a hyped pace.
- Lead with a bold claim or confrontational hook in the first sentence. No greetings, no intro.
- Sound like real sports banter: short sentences, direct address ("look", "I'm telling you"), rhetorical jabs.
- Keep the creator's actual opinion and stance. Sharpen it, don't change it.
- Plain spoken text only: no emojis, no hashtags, no stage directions, no quotes.
- Also produce a short ALL-CAPS on-screen headline, max 6 words, capturing the take.
  Weave 1-2 fitting emojis INTO the headline where they hit hardest (after a key
  word or at the end) — like real Reels captions.
- Also pick ONE emoji that captures the vibe of the take (like 😤 🔥 💀 🐐 😭 🤡).
- Also art-direct the clip:
  * "colors": exactly 3 hex colors for an animated background gradient. Rich,
    saturated jewel tones evoking the sport/team/mood (team colors welcome).
    Medium-dark only — never white, pastel or light colors (white text must stay
    readable), and never black or near-black (the video must feel colorful, not
    gloomy). Order = top to bottom.
  * "accent": 1 bright hex color for the highlighted caption word — must pop
    against black chip boxes (think neon green, cyan, gold, hot pink).

Respond with JSON:
{"headline": "...", "script": "...", "emoji": "...",
 "colors": ["#RRGGBB", "#RRGGBB", "#RRGGBB"], "accent": "#RRGGBB"}"""

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _hex(value, fallback: str) -> str:
    value = str(value or "").strip()
    return ("#" + value.lstrip("#")).upper() if HEX_RE.match(value) else fallback


def _fix_luma(hex_color: str, min_luma: float = 0.15, max_luma: float = 0.42) -> str:
    """Keep background colors in a readable, colorful band: bright enough to
    not read as black, dark enough that white text stays readable."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    # Dark AND colorless (black/charcoal) has no hue to lift — swap for a rich tone
    if luma < min_luma and max(r, g, b) - min(r, g, b) < 16:
        return "#3D2C8D"
    if luma > max_luma:
        k = max_luma / luma
    elif luma < min_luma:
        k = min_luma / luma
    else:
        return hex_color.upper()
    r, g, b = (min(255, round(c * k)) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def write_script(
    take: str,
    sport: str,
    tone: str,
    content_type: str = "Hot Take",
    seconds: int = config.TARGET_SECONDS,
    notes: str = "",
) -> dict:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    # ~3.1 spoken words/second at banter pace
    min_words, max_words = round(seconds * 2.7), round(seconds * 3.2)
    user_msg = f"Sport: {sport}\nContent type: {content_type}\nTone: {tone}\nOpinion: {take}"
    if notes:
        user_msg += f"\nCreator notes (follow them): {notes}"
    kwargs: dict = {
        "model": config.SCRIPT_MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                # .replace, not .format — the prompt contains literal JSON braces
                "content": SYSTEM_PROMPT.replace("{min_words}", str(min_words))
                .replace("{max_words}", str(max_words))
                .replace("{seconds}", str(max(1, seconds - 1))),
            },
            {"role": "user", "content": user_msg},
        ],
    }
    if config.SCRIPT_MODEL.startswith("gpt-5"):
        kwargs["reasoning_effort"] = "low"  # snappy; gpt-5.x rejects temperature
    else:
        kwargs["temperature"] = 0.9
    resp = client.chat.completions.create(**kwargs)
    data = json.loads(resp.choices[0].message.content)
    headline = str(data.get("headline", "")).strip().upper()[:60]
    script = " ".join(str(data.get("script", "")).split())
    if not script:
        raise ValueError("script model returned empty script")
    emoji = str(data.get("emoji", "")).strip() or "🔥"
    raw_colors = data.get("colors") or []
    defaults = ["#7B2FF7", "#C13584", "#F03A70"]
    colors = [
        _fix_luma(_hex(raw_colors[i] if i < len(raw_colors) else None, defaults[i]))
        for i in range(3)
    ]
    accent = _hex(data.get("accent"), "#32E77B")
    return {
        "headline": headline,
        "script": script,
        "emoji": emoji,
        "colors": colors,
        "accent": accent,
    }
