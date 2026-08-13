"""Take enhancement — two fresh variations, on demand.

Sits on the input page, before anything is generated. The user keeps their
original take visible at all times and may ask for variations as many times as
they like; each request returns two NEW ones, so the feature is a slot machine
they control rather than a correction they have to accept.

Two, not one and not five. One reads as "the AI rewrote you" and gets
accepted or dismissed; five is a menu nobody reads. Two invites comparison,
which is the cheapest decision a person can make.

Temperature is high and rising with each round: identical settings would give
near-identical suggestions on the second click, which reads as broken.
"""

from __future__ import annotations

import json
import logging
import re

from .types import _clean

log = logging.getLogger("banter.video.takes")

VARIATIONS = 2
MAX_TAKE_CHARS = 280
# Round 1 is already loose; later rounds push further so repeat clicks feel
# like new ideas rather than rephrasings of the same one.
BASE_TEMPERATURE = 0.9
TEMPERATURE_STEP = 0.15
MAX_TEMPERATURE = 1.3

TAKE_ENHANCER_SYSTEM = """\
You are an Instagram Sports Banter specialist. You rewrite a fan's sports
opinion into a take that would stop a thumb mid-scroll and start an argument
in the comments.

<what_you_are_optimising_for>
Reach comes from shares and comments, not from likes. A take earns those by
being (a) instantly understood, (b) funny or savage enough to quote, and
(c) disagreeable enough that someone feels compelled to reply. A take nobody
argues with is a take nobody spreads.
</what_you_are_optimising_for>

<rules>
- NEVER reverse, soften, or hedge the user's stance. You sharpen their
  opinion; you do not correct it. If they say a team is bad, your version
  says it harder.
- Front-load the hook. The first four or five words must carry the whole
  claim, because that is all a scrolling viewer reads.
- Be specific, not abstract. Name the player, the team, the moment, the
  habit. "The Lakers are frauds" is weaker than "The Lakers play defence
  like the arena charges them per effort."
- Make it VISUAL. This becomes a comedy video, so the take should imply a
  scene someone could film — a person doing something absurd — not an
  abstract judgement.
- Sound like a fan in a group chat: confident, conversational, a little
  unhinged. Never like a brand, a headline, or a sports broadcaster.
- Comedy comes from exaggeration and specificity, never from puns.
- Under 200 characters. Shorter usually hits harder.
- Never state a real score, result, injury, trade or quote as fact.
- Never insult a person's appearance, family, race, or intelligence. Mock
  performance, decisions and situations only.
</rules>

<variation_strategy>
Return exactly two takes that differ in ANGLE, not in wording. Pick two of:
- the absurd exaggeration (push the claim to its ridiculous extreme)
- the specific accusation (one concrete recurring habit, named)
- the mock-sympathy (pretend to defend them, condescendingly)
- the confident prediction (state the future as settled fact)
- the comparison (measure them against something humiliating)
Never return two takes that are the same angle reworded.
</variation_strategy>

Return ONLY JSON:
{"takes": [
  {"take": "...", "angle": "two or three words naming the angle used",
   "why": "one short line on what makes this one spread"},
  {"take": "...", "angle": "...", "why": "..."}
]}"""


def variations(take: str, sport: str, tone: str, client=None, round_index: int = 0) -> list[dict]:
    """Two enhanced takes. Never raises; returns [] when nothing is available.

    `round_index` is how many times the user has already asked, and only
    raises the temperature — the caller decides what to do with an empty list
    (keep the original, which is always the safe outcome).
    """
    take = _clean(take)
    if not take or client is None or not getattr(client, "available", False):
        return []

    temperature = min(MAX_TEMPERATURE, BASE_TEMPERATURE + TEMPERATURE_STEP * max(0, round_index))
    user = (
        f"Sport: {sport}\n"
        f"Tone to write in: {tone}\n"
        f"The fan's original take: {take}\n\n"
        f"Give me two sharper versions, in different angles."
    )
    try:
        raw = client.complete_json(
            TAKE_ENHANCER_SYSTEM, user, max_tokens=2000, temperature=temperature
        )
        parsed = _parse(raw)
    except Exception:  # noqa: BLE001 — the original take is always the fallback
        log.exception("take enhancement failed")
        return []

    out: list[dict] = []
    for item in parsed[:VARIATIONS]:
        text = _clean(item.get("take"))[:MAX_TAKE_CHARS]
        if not text or text.lower() == take.lower():
            continue
        out.append({
            "take": text,
            "angle": _clean(item.get("angle"))[:40],
            "why": _clean(item.get("why"))[:140],
        })
    return out


def _parse(text: str | None) -> list[dict]:
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
    items = data.get("takes") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    return [i if isinstance(i, dict) else {"take": str(i)} for i in items]
