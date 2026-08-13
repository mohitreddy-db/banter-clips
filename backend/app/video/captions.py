"""Instagram caption suggestions.

The video is the work; the caption is the thing people actually stall on at
the moment of publishing. Three options beat one — a single suggestion gets
accepted or discarded, whereas a short list gets *picked between*, which is a
much easier decision and produces better captions than an empty box.

Cheap (one small text call, a fraction of a cent) and never blocking: with no
model, a bad response, or an exception, callers get sensible deterministic
fallbacks built from the take itself.
"""

from __future__ import annotations

import json
import logging
import re

from .types import _clean

log = logging.getLogger("banter.video.captions")

MAX_CAPTION_CHARS = 300
SUGGESTION_COUNT = 3

CAPTION_SYSTEM = """\
You write Instagram captions for short sports-comedy videos.

Return THREE captions in different registers:
1. punchy — one short line, the take sharpened to its edge
2. conversational — invites replies, ends in a question
3. hype — loud, confident, celebratory

Rules for every caption:
- under 150 characters before the hashtags
- keep the take's stance; never reverse or soften it
- sound like a fan posting, not a brand advertising
- 2 to 4 lowercase hashtags at the end, specific to the sport, teams and
  players involved — no generic #viral #fyp #explore filler
- no emoji spam: at most one, and only if it earns its place
- never claim a real result, score, quote or news event happened

Return ONLY JSON:
{"captions": ["...", "...", "..."]}"""


def suggest(take: str, sport: str, tone: str, client=None) -> list[str]:
    """Three caption options. Never raises, never returns an empty list."""
    take = _clean(take)
    options: list[str] = []

    if client is not None and getattr(client, "available", False) and take:
        try:
            user = f"Sport: {sport}\nTone: {tone}\nThe take in the video: {take}"
            options = _parse(client.complete_json(CAPTION_SYSTEM, user))
        except Exception:  # noqa: BLE001 — suggestions are never load-bearing
            log.exception("caption suggestion failed; using fallbacks")

    options = [c for c in (_clean(o)[:MAX_CAPTION_CHARS] for o in options) if c]
    for fallback in _fallbacks(take, sport):
        if len(options) >= SUGGESTION_COUNT:
            break
        if fallback not in options:
            options.append(fallback)
    return options[:SUGGESTION_COUNT]


def _parse(text: str | None) -> list[str]:
    if not text:
        return []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", str(text), re.S)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    captions = data.get("captions") if isinstance(data, dict) else data
    return [str(c) for c in captions][:6] if isinstance(captions, list) else []


def _fallbacks(take: str, sport: str) -> list[str]:
    """Deterministic options, so the picker is never empty."""
    tag = {"NBA": "#nba #hoops", "NFL": "#nfl #football",
           "Soccer": "#soccer #football", "MLB": "#mlb #baseball"}.get(sport, "#sports")
    trimmed = take.rstrip(".")
    return [
        f"{trimmed}. {tag}",
        f"{trimmed} — tell me I'm wrong. {tag}",
        f"Said what I said. {trimmed} {tag}",
    ]
