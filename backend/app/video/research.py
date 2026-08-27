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

We are going to render this person wearing their real kit, so the club, the
squad number and the kit description have to be right — a confidently wrong
number looks worse on screen than a vague one.

Pick the kit people PICTURE when they hear the name. For an active player
that is their current club; for a retired or legacy figure it is the team
they are iconically associated with (e.g. Ronaldinho → the yellow Brazil 10
or Barcelona years, never a minor later affiliation). Describe their
appearance from that same era.

Return ONLY a JSON object, no prose:

{{"found": true/false,
  "role": "player" | "manager" | "other",
  "look": "one detailed sentence on physical appearance: build, height impression, hair, facial hair, skin tone, distinctive features",
  "team": "their current club or franchise, or empty string",
  "number": "their current squad number as digits, or empty string (always empty for managers)",
  "kit": "what THIS person actually wears on duty. A player: their club's current home kit — colours, pattern, crest. A MANAGER or coach: their touchline look — club training quarter-zip/jacket with the crest, or the suit they're known for — NEVER a player's shirt",
  "team_colors": ["primary", "colours"],
  "voice_style": "three or four words describing how they speak"}}

If you cannot identify the person, return {{"found": false}}. If you are
unsure of the number, return an empty string rather than guessing."""


def enabled() -> bool:
    return (
        getattr(settings, "WEB_RESEARCH", "off") == "openai"
        and bool(getattr(settings, "OPENAI_API_KEY", ""))
    )


# Words that mark a planner-invented GENERIC character rather than a person.
_GENERIC_WORDS = re.compile(
    r"\b(?:random|generic|fan|fans|supporter|defender|goalkeeper|keeper|"
    r"striker|midfielder|player|referee|umpire|official|coach|manager|"
    r"reporter|announcer|commentator|steward|mascot|crowd|teammate|"
    r"opponent|rival)\b",
    re.IGNORECASE,
)


def looks_like_real_person(name: str) -> bool:
    """Is this name worth researching and persisting as a real person?

    A planner may cast "random La Liga defender" or "a die-hard fan" — web
    search will happily 'find' somebody for those, dressing a generic
    character in a real player's kit and number (observed 2026-08-20).
    Generic characters keep their planner-authored description instead.
    """
    name = str(name or "").strip()
    words = name.split()
    if not words or len(words) > 4:
        return False
    if _GENERIC_WORDS.search(name):
        return False
    if words[0].lower() in ("a", "an", "the", "some", "one"):
        return False
    # Real names arrive capitalised ("Ronaldinho", "Lamine Yamal").
    return all(w[:1].isupper() or not w[:1].isalpha() for w in words)


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
    # Build the wardrobe from the most specific thing we got back. A named kit
    # beats a colour palette, and a real squad number beats none — those are
    # what the image model renders as legible lettering.
    kit = _clean(data.get("kit"))
    number = re.sub(r"[^0-9]", "", str(data.get("number") or ""))[:2]
    # A manager in a squad-numbered shirt reads instantly as wrong (observed:
    # Arteta rendered as a player). Staff wear carries no number.
    if _clean(data.get("role")).lower() in ("manager", "coach", "other"):
        number = ""
    colors = data.get("team_colors")
    palette = ""
    if isinstance(colors, list) and colors:
        palette = " and ".join(_clean(c) for c in colors[:2] if _clean(c))

    base = kit or (f"an authentic {palette} team kit" if palette else "")
    if base:
        numbered = f", the number {number} on the front" if number else ""
        member.wardrobe = f"{base}{numbered}, crisp legible lettering"
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
