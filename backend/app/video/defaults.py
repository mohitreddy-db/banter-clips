"""Input resolution — the first line of defence against missing data.

Nothing downstream is allowed to see a null, an empty string, or an
out-of-range number. Whatever arrives, this produces a complete brief.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog, focus as focus_mod
from .library import default_venue
from .types import _clean

# One vocabulary for the whole app: the DB check constraints, the API
# schemas and these are all built from models.SPORTS / models.TONES, so a
# sport can only be added in one place.
from ..models import SPORTS, TONES  # noqa: E402
# The product's duration tiers. These must match the options the UI offers and
# the Literal on ClipCreate — a mismatch means a user picks a length and
# silently gets a different one. Free tops out at 15s; 30s is Creator-only.
DURATIONS = (10, 15, 30)

DEFAULT_SPORT = "Soccer"
DEFAULT_TONE = "Bold"
DEFAULT_SECONDS = 15
# Matches the clips_take_len check constraint in the database.
MIN_TAKE_CHARS = 10
GENERIC_TAKE = "This team is not as good as everyone thinks."
# Duration -> shot count. The Mourinho reference (analyzed frame-by-frame,
# see VIDEO-REALISM-PLAN.md) mixes one long dialogue "anchor" shot with
# short reaction cutaways in ONE persistent location — so shots are no
# longer uniform: the planner gives the anchor 5-8s and cutaways 2.5-4s.
# Grok's reliable window is 4-8s/generation, and rerolling a 3s cutaway is
# cheap.
SHOT_COUNTS = {10: 3, 15: 4, 30: 7}
TARGET_SCENE_SECONDS = 4.5   # fallback for unmapped durations
MIN_SCENES, MAX_SCENES = 2, 12


@dataclass
class ResolvedInput:
    take: str
    sport: str
    tone: str
    seconds: int
    scene_count: int
    venue: str
    focus: focus_mod.Focus = field(default_factory=focus_mod.Focus)
    # The user's optional extras: other sports the take spans, and teams or
    # players they explicitly asked to see. Requirements when present.
    also_sports: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "take": self.take, "sport": self.sport, "tone": self.tone,
            "also_sports": self.also_sports, "subjects": self.subjects,
            "seconds": self.seconds, "scene_count": self.scene_count,
            "focus": self.focus.to_dict(),
        }


def resolve(
    take: object = None,
    sport: object = None,
    tone: object = None,
    seconds: object = None,
    also_sports: list | None = None,
    subjects: list | None = None,
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
    count = SHOT_COUNTS.get(resolved_seconds) or max(
        MIN_SCENES, min(MAX_SCENES, round(resolved_seconds / TARGET_SCENE_SECONDS))
    )

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
        also_sports=[s for s in (also_sports or []) if s in SPORTS and s != resolved_sport],
        subjects=[str(s).strip()[:60] for s in (subjects or []) if str(s).strip()][:8],
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
    # Otherwise the shared marker table (video/sports.py), which covers all
    # twelve sports rather than the original four.
    from . import sports as sports_mod

    return sports_mod.infer(take)


def _seconds(value: object) -> int:
    try:
        n = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_SECONDS
    if n <= 0:
        return DEFAULT_SECONDS
    # Snap to the product's duration tiers (15 / 30 / 60 / 90).
    return min(DURATIONS, key=lambda tier: abs(tier - n))
