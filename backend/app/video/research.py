"""Optional web research — filling gaps the catalog can't.

When a plan casts someone who is NOT in the curated catalog, their look is
synthesised from the name alone ("<name>, a professional NBA figure"), which
renders a generic stand-in. With research enabled, one web-search call fetches
enough public facts (appearance, current team, team colours) to write a real
look description before any money is spent on images.

Uses the OpenAI Responses API with the built-in `web_search` tool. Strictly
optional and strictly non-fatal: off by default (`WEB_RESEARCH=off`), and any
error simply leaves the cast member as it was.

Never used for scores, results, or quotes — the planner is forbidden from
presenting invented facts as news, and research only describes appearance.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from ..config import settings
from .types import CastMember, _clean

log = logging.getLogger("banter.video.research")

RESPONSES_URL = "https://api.openai.com/v1/responses"

RESEARCH_PROMPT = """\
Search the web for the athlete or sports figure "{name}" ({sport}).
Return ONLY a JSON object, no prose:

{{"found": true/false,
  "look": "one detailed sentence describing their physical appearance: build, height impression, hair, facial hair, skin tone, distinctive features",
  "team": "their current team name, or empty string",
  "team_colors": ["primary", "colours"],
  "voice_style": "three or four words describing how they speak"}}

If you cannot identify the person, return {{"found": false}}."""


def enabled() -> bool:
    return (
        getattr(settings, "WEB_RESEARCH", "off") == "openai"
        and bool(getattr(settings, "OPENAI_API_KEY", ""))
    )


def enrich_member(member: CastMember, sport: str) -> bool:
    """Improve an off-catalog cast member's look in place.

    Returns True when something was actually improved. Never raises.
    """
    if not enabled():
        return False
    try:
        data = _search(member.name, sport)
    except Exception:  # noqa: BLE001 — research is a bonus, never a blocker
        log.exception("web research failed for %s", member.name)
        return False
    if not data or not data.get("found"):
        return False

    look = _clean(data.get("look"))
    if look:
        member.look = look
    colors = data.get("team_colors")
    if isinstance(colors, list) and colors:
        palette = " and ".join(_clean(c) for c in colors[:2] if _clean(c))
        if palette:
            member.wardrobe = (
                f"an authentic {palette} team kit with crest, name and number, crisp legible lettering"
            )
    voice = _clean(data.get("voice_style"))
    if voice:
        member.voice = voice
    return bool(look)


def _search(name: str, sport: str) -> dict | None:
    body = {
        "model": getattr(settings, "OPENAI_RESEARCH_MODEL", "gpt-4.1-mini"),
        "tools": [{"type": "web_search"}],
        "input": RESEARCH_PROMPT.format(name=name, sport=sport),
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            RESPONSES_URL, json=body,
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        )
    if resp.status_code >= 400:
        log.warning("research -> %s %s", resp.status_code, resp.text[:300])
        return None
    return _extract_json(resp.json())


def _extract_json(payload: dict) -> dict | None:
    """Pull the model's text out of a Responses API payload and parse it."""
    texts: list[str] = []
    for item in payload.get("output") or []:
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part["text"]))
    blob = "\n".join(texts)
    match = re.search(r"\{.*\}", blob, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
