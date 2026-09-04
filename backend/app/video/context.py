"""Storyline Pack — real-world context fetched before planning.

The frame-by-frame study of the viral reference (VIDEO-REALISM-PLAN.md §1)
showed the wow factor is context: the actual current squad, this week's
storylines, the real kit and sponsor, a real place, the person's famous
mannerisms. Our planner used to know none of that.

One web-search round (Firecrawl, falling back to the OpenAI `web_search`
tool — see websearch.py) fetches a structured pack; packs are cached in Postgres per
topic per day, so a hot take about the same team costs ~$0 after the first
video. Strictly optional and strictly non-fatal: no key, a bad response, or
a timeout simply yields no pack, and the planner works as before.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

from ..config import settings
from . import catalog, websearch

log = logging.getLogger("banter.video.context")

PACK_PROMPT = """\
Search the web for the CURRENT situation around: {topic} ({sport}).
Today's date: {today}. A comedy video script will be built on this, so the
value is what is true and talked about RIGHT NOW.

Return ONLY a JSON object, no prose:

{{"found": true/false,
  "entities": {{"players": ["3-6 current key players, most famous first"],
               "manager": "current head coach/manager or empty",
               "club": "full club/franchise name or empty"}},
  "recent": ["2-4 short factual items from the last 1-2 weeks: results,
             signings, injuries, records — each one sentence"],
  "storylines": ["2-4 things fans are currently joking or arguing about —
                 the memes, the frustrations, the debates"],
  "kit": "one clause: current kit colours, shirt sponsor wordmark and maker
          (e.g. 'white shirt, Emirates FLY BETTER across the chest, adidas')",
  "places": ["1-3 real, visually specific settings tied to this topic —
             training ground look, stadium name and look, press room"],
  "personas": {{"<person>": "their famous mannerisms/persona in a few words
               (e.g. 'taps his watch, arms folded, calls himself the
               Special One')"}},
  "avoid": ["anything that would read as fake, tasteless or wrong to fans
            right now (recent tragedies, ongoing legal cases)"]}}

Rules: only include what search results support; empty lists over guesses;
never invent scores or quotes. If the topic is unrecognisable, return
{{"found": false}}."""


def enabled() -> bool:
    return (
        str(getattr(settings, "STORYLINE_CONTEXT", "on")).lower() == "on"
        and websearch.enabled()
    )


def topic_for(take: str, sport: str) -> str:
    """A cache-friendly topic: detected teams/players, else the sport."""
    chars, teams = catalog.find_mentions(take, sport)
    names = [t.name for t in teams[:2]] + [c.name for c in chars[:2]
                                           if not c.name.startswith(("a ", "an ", "the "))]
    if names:
        return ", ".join(dict.fromkeys(names))
    # No catalog hit: use capitalised words from the take as the topic seed
    # ("Arsenal bottled it" → "Arsenal"), else just the sport.
    words = re.findall(r"\b[A-Z][a-zA-Z]{3,}\b", take)
    return ", ".join(dict.fromkeys(words[:3])) or sport


def get_pack(take: str, sport: str) -> dict | None:
    """The Storyline Pack for this take, cached per topic per day.

    Never raises; None means 'no context, plan without it'."""
    if not enabled():
        return None
    topic = topic_for(take, sport)
    key = re.sub(r"[^a-z0-9]+", "-", f"{sport}-{topic}".lower()).strip("-")[:120]
    try:
        cached = _cache_get(key)
        if cached is not None:
            return cached
        pack = _fetch(topic, sport)
        if pack and pack.get("found"):
            _cache_put(key, pack)
            return pack
        return None
    except Exception:  # noqa: BLE001 — context is a bonus, never a blocker
        log.exception("storyline pack failed for %r", topic)
        return None


def summarize(pack: dict | None) -> str:
    """The pack as a planner-ready context block. Empty string when absent."""
    if not pack:
        return ""
    lines = ["Real-world context, verified by web search TODAY. Build the "
             "story on it — this is what makes the video feel real:"]
    ent = pack.get("entities") or {}
    people = ", ".join(ent.get("players") or [])
    if people:
        lines.append(f"- Current key players: {people}")
    if ent.get("manager"):
        lines.append(f"- Current manager: {ent['manager']}")
    for item in (pack.get("recent") or [])[:4]:
        lines.append(f"- Recent: {item}")
    for item in (pack.get("storylines") or [])[:4]:
        lines.append(f"- Fans right now: {item}")
    if pack.get("kit"):
        lines.append(f"- Authentic kit: {pack['kit']}")
    for place in (pack.get("places") or [])[:3]:
        lines.append(f"- Real setting available: {place}")
    for who, bit in (pack.get("personas") or {}).items():
        lines.append(f"- Persona ({who}): {bit}")
    for item in (pack.get("avoid") or [])[:3]:
        lines.append(f"- AVOID: {item}")
    return "\n".join(lines)


# ------------------------------------------------------------------ plumbing

def _fetch(topic: str, sport: str) -> dict | None:
    prompt = PACK_PROMPT.format(topic=topic, sport=sport, today=date.today().isoformat())
    answer = websearch.ask(prompt, [
        websearch.SearchSpec(f"{topic} {sport} latest news", limit=8, recent="week"),
        # Kit sponsor wordmarks and stadium looks rarely fit a snippet.
        websearch.SearchSpec(f"{topic} {sport} squad kit sponsor stadium", limit=5, scrape_top=2),
    ], timeout=60.0, max_tokens=2500)
    return answer.data


def _cache_get(key: str) -> dict | None:
    from ..db import SessionLocal
    from ..models import StorylinePack

    db = SessionLocal()
    try:
        row = (db.query(StorylinePack)
               .filter(StorylinePack.topic_key == key,
                       StorylinePack.day == date.today())
               .first())
        return dict(row.pack) if row else None
    finally:
        db.close()


def _cache_put(key: str, pack: dict) -> None:
    from ..db import SessionLocal
    from ..models import StorylinePack

    db = SessionLocal()
    try:
        db.add(StorylinePack(topic_key=key, day=date.today(), pack=pack))
        db.commit()
    except Exception:  # noqa: BLE001 — a cache miss next time is the only cost
        log.warning("could not cache storyline pack %r", key)
    finally:
        db.close()
