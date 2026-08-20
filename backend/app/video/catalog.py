"""Character & team catalog — the data behind likeness and team identity.

The catalog is two JSON files plus a folder of AI-generated reference stills
(`catalog/characters.json`, `catalog/teams.json`, `catalog/references/`).
Design rules, from VIDEO-GENERATION-PLAN.md §5:

- Team identity is the AUTHENTIC kit: real colours, crest, name and number.
  Measured — asking for the real kit renders clean lettering; banning
  lettering renders gibberish, and the specificity is what makes a frame
  look like real footage.
- Reference stills are AI-generated with the SAME image model used for scene
  keyframes (see `catalog_build.py`), so a reference and a keyframe share a
  visual dialect.
- The catalog never fails a job. Unreadable JSON degrades to an empty catalog
  and callers fall back to text-only descriptions.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .types import CastMember, _clean

log = logging.getLogger("banter.video.catalog")

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
REFERENCES_DIR = CATALOG_DIR / "references"

# Appended when a team has no explicit jersey_description. Asking for the real
# kit is what produces clean lettering; asking for none produces gibberish.
NO_TEXT_RULE = "crisp legible lettering"


@dataclass
class Character:
    id: str
    name: str
    sport: str = "NBA"
    teams: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    look: str = ""
    default_wardrobe: str = ""
    voice_style: str = "neutral, conversational"
    reference_images: list[str] = field(default_factory=list)
    active: bool = True

    def reference_paths(self) -> list[Path]:
        """Only references that actually exist on disk."""
        paths = []
        for rel in self.reference_images:
            p = CATALOG_DIR / rel
            if p.exists():
                paths.append(p)
        return paths


@dataclass
class Team:
    id: str
    name: str
    sport: str = "NBA"
    aliases: list[str] = field(default_factory=list)
    primary_colors: list[str] = field(default_factory=list)
    secondary_colors: list[str] = field(default_factory=list)
    jersey_description: str = ""
    venues: list[str] = field(default_factory=list)
    associated_players: list[str] = field(default_factory=list)
    active: bool = True

    def palette(self) -> str:
        return " and ".join(self.primary_colors) or "team-coloured"

    def wardrobe(self) -> str:
        """Jersey text for prompts; always asks for legible lettering."""
        base = _clean(self.jersey_description) or (
            f"the authentic {self.name} {self.palette()} kit with crest, name and number"
        )
        if NO_TEXT_RULE.split(",")[0] not in base:
            base = f"{base}, {NO_TEXT_RULE}"
        return base


# ------------------------------------------------------------------- loading

@lru_cache(maxsize=1)
def characters() -> dict[str, Character]:
    return {c.id: c for c in _load_characters() if c.active}


@lru_cache(maxsize=1)
def teams() -> dict[str, Team]:
    return {t.id: t for t in _load_teams() if t.active}


def reload() -> None:
    """Drop caches after editing the JSON files (used by catalog_build)."""
    characters.cache_clear()
    teams.cache_clear()


# Runtime-discovered characters live in an OVERLAY file, not characters.json:
# the main file is in git and a deploy's `git pull` would clobber runtime
# writes. The overlay is gitignored, merged on load (curated ids win), and is
# what the future admin catalog page will curate from.
OVERLAY_PATH = CATALOG_DIR / "characters.local.json"


def _load_characters() -> list[Character]:
    out = []
    seen: set[str] = set()
    for path in (CATALOG_DIR / "characters.json", OVERLAY_PATH):
        for char in _parse_characters(_read_entries(path, "characters")):
            if char.id not in seen:
                seen.add(char.id)
                out.append(char)
    return out


def _parse_characters(entries: list[dict]) -> list[Character]:
    out = []
    for raw in entries:
        try:
            out.append(Character(
                id=_clean(raw.get("id")),
                name=_clean(raw.get("name"), "the player"),
                sport=_clean(raw.get("sport"), "NBA"),
                teams=_strs(raw.get("teams")),
                aliases=[a.lower() for a in _strs(raw.get("aliases"))],
                look=_clean(raw.get("look")),
                default_wardrobe=_clean(raw.get("default_wardrobe")),
                voice_style=_clean(raw.get("voice_style"), "neutral, conversational"),
                reference_images=_strs(raw.get("reference_images")),
                active=bool(raw.get("active", True)),
            ))
        except Exception:  # noqa: BLE001 — one bad entry must not sink the file
            log.exception("skipping malformed character entry")
    return [c for c in out if c.id]


def _load_teams() -> list[Team]:
    out = []
    for raw in _read_entries(CATALOG_DIR / "teams.json", "teams"):
        try:
            out.append(Team(
                id=_clean(raw.get("id")),
                name=_clean(raw.get("name"), "the team"),
                sport=_clean(raw.get("sport"), "NBA"),
                aliases=[a.lower() for a in _strs(raw.get("aliases"))],
                primary_colors=_strs(raw.get("primary_colors")),
                secondary_colors=_strs(raw.get("secondary_colors")),
                jersey_description=_clean(raw.get("jersey_description")),
                venues=_strs(raw.get("venues")),
                associated_players=_strs(raw.get("associated_players")),
                active=bool(raw.get("active", True)),
            ))
        except Exception:  # noqa: BLE001
            log.exception("skipping malformed team entry")
    return [t for t in out if t.id]


def _read_entries(path: Path, key: str) -> list[dict]:
    """Never raises. A missing or corrupt file is an empty catalog."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        entries = data.get(key) if isinstance(data, dict) else data
        return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
    except Exception:  # noqa: BLE001
        log.warning("catalog file %s unreadable; continuing without it", path.name)
        return []


def _strs(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(v) for v in value if _clean(v)]


# ------------------------------------------------- dynamic (runtime) entries

def save_dynamic_character(member: CastMember, sport: str) -> Character | None:
    """Persist a researched off-catalog cast member into the overlay.

    Called after web research confirmed WHO this is and wrote a real look and
    kit, so the entry meets the same bar as a curated one. Ronaldinho and
    Ronaldo stay separate people: the id comes from the member's own id/name,
    and an id already in the catalog is never overwritten here — curation
    wins over discovery. Returns the loaded Character (existing or new).
    Never raises.
    """
    try:
        char_id = re.sub(r"[^a-z0-9]+", "_", (member.id or member.name).lower()).strip("_")[:40]
        if not char_id:
            return None
        existing = characters().get(char_id)
        if existing:
            return existing
        entry = {
            "id": char_id,
            "name": _clean(member.name, char_id.replace("_", " ").title()),
            "sport": _clean(sport, "NBA"),
            "teams": [],
            "aliases": [],
            "look": _clean(member.look),
            "default_wardrobe": _clean(member.wardrobe),
            "voice_style": _clean(member.voice, "neutral, conversational"),
            "reference_images": [],
            "active": True,
            "source": "auto-research",   # the admin page will surface these
        }
        data = {"characters": []}
        if OVERLAY_PATH.exists():
            try:
                data = json.loads(OVERLAY_PATH.read_text())
            except json.JSONDecodeError:
                log.warning("overlay unreadable; starting a fresh one")
        entries = data.setdefault("characters", [])
        entries[:] = [e for e in entries if e.get("id") != char_id]
        entries.append(entry)
        OVERLAY_PATH.write_text(json.dumps(data, indent=2) + "\n")
        reload()
        log.info("catalog: added dynamic character %r (%s)", char_id, entry["name"])
        return characters().get(char_id)
    except Exception:  # noqa: BLE001 — persistence is a bonus, never a blocker
        log.exception("could not persist dynamic character %r", member.name)
        return None


def set_reference_images(char_id: str, reference_paths: list[str]) -> None:
    """Record generated stills for an overlay character. Never raises."""
    try:
        if not OVERLAY_PATH.exists():
            return
        data = json.loads(OVERLAY_PATH.read_text())
        for entry in data.get("characters", []):
            if entry.get("id") == char_id:
                entry["reference_images"] = reference_paths
        OVERLAY_PATH.write_text(json.dumps(data, indent=2) + "\n")
        reload()
    except Exception:  # noqa: BLE001
        log.exception("could not record references for %r", char_id)


# -------------------------------------------------------------------- lookup

def characters_for(sport: str) -> list[Character]:
    return [c for c in characters().values() if c.sport == sport]


def teams_for(sport: str) -> list[Team]:
    return [t for t in teams().values() if t.sport == sport]


def get_character(char_id: str) -> Character | None:
    return characters().get(_clean(char_id))


def get_team(team_id: str) -> Team | None:
    return teams().get(_clean(team_id))


def team_of(character: Character) -> Team | None:
    for team_id in character.teams:
        team = teams().get(team_id)
        if team:
            return team
    return None


def find_mentions(text: str, sport: str | None = None) -> tuple[list[Character], list[Team]]:
    """Which catalog characters and teams does this text name?

    Word-boundary matching on names and aliases, so "leo" matches "Leo cooked"
    but not "leopard". Used by focus detection; keep it deterministic.
    """
    blob = f" {re.sub(r'[^a-z0-9 ]+', ' ', str(text or '').lower())} "
    found_chars, found_teams = [], []
    for char in characters().values():
        if sport and char.sport != sport:
            continue
        if _mentioned(blob, [char.name.lower(), *char.aliases, *_surnames(char)]):
            found_chars.append(char)
    for team in teams().values():
        if sport and team.sport != sport:
            continue
        if _mentioned(blob, [team.name.lower(), *team.aliases]):
            found_teams.append(team)
    return found_chars, found_teams


# Name words that are also everyday English words; matching them bare would
# hit half of all takes ("this hurts", "the judge ruled", plain "james").
_AMBIGUOUS_NAME_WORDS = {"judge", "hurts", "james", "curry"}


def _surnames(char: Character) -> list[str]:
    """Individual name words that can stand alone ("Ohtani", "Mahomes").

    Archetypes ("a weary head coach") rely on aliases instead, and ambiguous
    words are excluded — those characters carry explicit aliases for the
    forms people actually type ("the judge", "chef curry").
    """
    name = char.name.lower()
    if name.startswith(("a ", "an ", "the ")):
        return []
    return [w for w in name.split()
            if len(w) >= 5 and w not in _AMBIGUOUS_NAME_WORDS]


def _mentioned(blob: str, terms: list[str]) -> bool:
    for term in terms:
        term = re.sub(r"[^a-z0-9 ]+", " ", term).strip()
        # Skip generic single words that would match half of all takes.
        if not term or (len(term) < 3 and " " not in term):
            continue
        if f" {term} " in blob:
            return True
    return False


def sport_of_mentions(text: str) -> str | None:
    """Infer the sport from catalog mentions — a Lakers take is an NBA take."""
    chars, mentioned_teams = find_mentions(text)
    votes: dict[str, int] = {}
    for item in [*chars, *mentioned_teams]:
        votes[item.sport] = votes.get(item.sport, 0) + 1
    if not votes:
        return None
    return max(votes, key=lambda s: votes[s])


# ---------------------------------------------------- prompt-facing helpers

def cast_member(char: Character, team: Team | None = None) -> CastMember:
    """A catalog character as the pipeline's CastMember, wearing the right kit.

    Team kit wins over the character's default wardrobe: a take about the
    Lakers should put everyone in purple and gold even if a player's default
    entry says otherwise.
    """
    wardrobe = team.wardrobe() if team else char.default_wardrobe
    if not wardrobe:
        wardrobe = f"an authentic team kit, {NO_TEXT_RULE}"
    return CastMember(
        id=char.id,
        name=char.name,
        look=char.look or f"{char.name}, a professional {char.sport} figure",
        wardrobe=wardrobe,
        voice=char.voice_style,
    )


_CLOSE_UP = re.compile(r"\b(close[- ]?up|tight|face|extreme close)\b", re.IGNORECASE)


def select_references(char: Character | None, camera: str = "") -> list[Path]:
    """Pick 1–2 reference stills for a keyframe (plan §5.7).

    Close-up framing prefers the face reference; anything else prefers the
    full-body one; with no signal, the first two listed. Only files that
    exist are returned, so an unbuilt catalog simply yields [].
    """
    if char is None:
        return []
    paths = char.reference_paths()
    if len(paths) <= 2:
        return paths

    def rank(p: Path) -> int:
        stem = p.stem.lower()
        if _CLOSE_UP.search(camera or ""):
            return 0 if "face" in stem else 1
        return 0 if ("full" in stem or "body" in stem) else 1

    return sorted(paths, key=rank)[:2]
