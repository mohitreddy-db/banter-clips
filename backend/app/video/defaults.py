"""Input resolution — the first line of defence against missing data.

Nothing downstream is allowed to see a null, an empty string, or an
out-of-range number. Whatever arrives, this produces a complete brief.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import catalog, focus as focus_mod
from .library import default_venue
from .types import _clean

SPORTS = ("NBA", "NFL", "Soccer", "MLB")
TONES = ("Funny", "Savage", "Hype", "Bold")
# The product's duration tiers (plan §2). Anything else snaps to the nearest.
DURATIONS = (15, 30, 60, 90)

DEFAULT_SPORT = "NBA"
DEFAULT_TONE = "Bold"
DEFAULT_SECONDS = 15
# Matches the clips_take_len check constraint in the database.
MIN_TAKE_CHARS = 10
GENERIC_TAKE = "This team is not as good as everyone thinks."
# Duration -> scene count. Keep clips long: fewer cuts means fewer voice and
# ambience seams, which is the dominant quality risk in multi-clip video.
TARGET_SCENE_SECONDS = 7.5
MIN_SCENES, MAX_SCENES = 2, 12

# Only used when the sport is missing entirely — a cheap keyword vote.
_SPORT_HINTS = {
    "NBA": ("nba", "basketball", "dunk", "three-pointer", "lakers", "knicks", "celtics",
            "warriors", "spurs", "lebron", "curry", "jokic", "wemby", "wembanyama",
            "brunson", "hoop", "courtside", "finals mvp"),
    "NFL": ("nfl", "football", "quarterback", "touchdown", "super bowl", "chiefs",
            "eagles", "mahomes", "sack", "end zone", "gridiron"),
    "Soccer": ("soccer", "premier league", "la liga", "champions league", "messi",
               "ronaldo", "world cup", "fifa", "offside", "penalty", "striker",
               "arsenal", "madrid", "barcelona", "yamal", "mbappe"),
    "MLB": ("mlb", "baseball", "home run", "pitcher", "world series", "yankees",
            "dodgers", "innings", "shortstop", "bullpen"),
}


@dataclass
class ResolvedInput:
    take: str
    sport: str
    tone: str
    seconds: int
    scene_count: int
    venue: str
    focus: focus_mod.Focus = field(default_factory=focus_mod.Focus)

    def to_dict(self) -> dict:
        return {
            "take": self.take, "sport": self.sport, "tone": self.tone,
            "seconds": self.seconds, "scene_count": self.scene_count,
            "focus": self.focus.to_dict(),
        }


def resolve(
    take: object = None,
    sport: object = None,
    tone: object = None,
    seconds: object = None,
) -> ResolvedInput:
    """Turn whatever we were given into a complete, valid brief."""
    clean_take = _clean(take)
    if len(clean_take) < MIN_TAKE_CHARS:
        # Empty, or too short to dramatise ("no", "lol"). Either way a video is
        # still owed, so substitute a generic take rather than failing.
        clean_take = GENERIC_TAKE
    clean_take = clean_take[:280]

    resolved_sport = _pick(sport, SPORTS) or _infer_sport(clean_take) or DEFAULT_SPORT
    resolved_tone = _pick(tone, TONES) or DEFAULT_TONE
    resolved_seconds = _seconds(seconds)
    count = max(MIN_SCENES, min(MAX_SCENES, round(resolved_seconds / TARGET_SCENE_SECONDS)))

    # Focus (plan §7.1): player / team / matchup / generic. A focused team
    # supplies the default venue, so team takes open somewhere on-brand.
    detected = focus_mod.detect(clean_take, resolved_sport)
    team = detected.primary_team
    venue = team.venues[0] if team and team.venues else default_venue(resolved_sport)

    return ResolvedInput(
        take=clean_take,
        sport=resolved_sport,
        tone=resolved_tone,
        seconds=resolved_seconds,
        scene_count=count,
        venue=venue,
        focus=detected,
    )


def _pick(value: object, allowed: tuple[str, ...]) -> str | None:
    """Case-insensitive membership, tolerant of stray whitespace."""
    text = _clean(value).lower()
    if not text:
        return None
    for option in allowed:
        if option.lower() == text:
            return option
    return None


def _infer_sport(take: str) -> str | None:
    # A catalog mention is the strongest signal: naming Wemby or the Lakers
    # settles the sport regardless of what other keywords appear.
    from_catalog = catalog.sport_of_mentions(take)
    if from_catalog in SPORTS:
        return from_catalog
    words = set(re.findall(r"[a-z']+", take.lower()))
    blob = take.lower()
    best, best_score = None, 0
    for sport, hints in _SPORT_HINTS.items():
        score = sum(1 for h in hints if (h in words) or (" " in h and h in blob))
        if score > best_score:
            best, best_score = sport, score
    return best


def _seconds(value: object) -> int:
    try:
        n = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_SECONDS
    if n <= 0:
        return DEFAULT_SECONDS
    # Snap to the product's duration tiers (15 / 30 / 60 / 90).
    return min(DURATIONS, key=lambda tier: abs(tier - n))
