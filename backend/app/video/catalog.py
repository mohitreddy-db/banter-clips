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
    source: str = "curated"  # "curated" | "auto-research" | "admin"

    def reference_paths(self) -> list[Path]:
        """Local files for this character's stills, downloading as needed.

        Entries are either repo-relative ("references/x.jpg", curated in git)
        or Supabase Storage keys ("catalog/references/x.jpg", the durable
        home of runtime-generated stills). Storage-backed stills are cached
        into the local references dir on first use — the pipeline reads
        bytes from disk. Never raises; an unfetchable still is skipped."""
        paths = []
        for entry in self.reference_images:
            if entry.startswith("references/"):
                p = CATALOG_DIR / entry
                if p.exists():
                    paths.append(p)
                continue
            cached = REFERENCES_DIR / Path(entry).name
            if cached.exists():
                paths.append(cached)
                continue
            try:
                from ..services import storage

                payload = storage.get().open(entry)
                if payload:
                    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
                    cached.write_bytes(payload)
                    paths.append(cached)
            except Exception:  # noqa: BLE001 — a missing still degrades, never fails
                log.warning("could not fetch reference %s", entry)
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


# Two-layer catalog. The curated JSON ships with the code; the DB layer
# (catalog_characters) is written at runtime — auto-research discoveries and
# admin-panel edits — and OVERRIDES a curated entry with the same id, so the
# admin page can edit or deactivate anything. DB rows plus Storage-hosted
# stills survive droplet rebuilds and are shared across API and worker.
def _load_characters() -> list[Character]:
    by_id = {c.id: c for c in _parse_characters(
        _read_entries(CATALOG_DIR / "characters.json", "characters"))}
    for char in _load_db_characters():
        by_id[char.id] = char
    return list(by_id.values())


def _load_db_characters() -> list[Character]:
    """Rows from catalog_characters. Never raises — no DB, no dynamic layer."""
    try:
        from ..db import SessionLocal
        from ..models import CatalogCharacter

        db = SessionLocal()
        try:
            rows = db.query(CatalogCharacter).all()
        finally:
            db.close()
        return [Character(
            id=r.id, name=r.name, sport=r.sport,
            teams=list(r.teams or []), aliases=[a.lower() for a in (r.aliases or [])],
            look=r.look, default_wardrobe=r.default_wardrobe,
            voice_style=r.voice_style or "neutral, conversational",
            reference_images=list(r.reference_images or []),
            active=bool(r.active), source=r.source or "admin",
        ) for r in rows]
    except Exception:  # noqa: BLE001 — the curated catalog must still load
        log.warning("catalog DB layer unavailable; using curated entries only")
        return []


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

def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")[:40]


def upsert_character(char_id: str, fields: dict, source: str = "admin") -> Character | None:
    """Create or update a DB catalog row (the layer that overrides curated).

    `fields` may hold any of: name, sport, look, default_wardrobe,
    voice_style, aliases, teams, reference_images, active. Missing fields on
    a NEW row are seeded from the curated entry of the same id, so an admin
    edit of a curated character starts from what ships in git. Never raises.
    """
    try:
        from ..db import SessionLocal
        from ..models import CatalogCharacter

        char_id = slugify(char_id)
        if not char_id:
            return None
        db = SessionLocal()
        try:
            row = db.get(CatalogCharacter, char_id)
            if row is None:
                base = characters().get(char_id)
                row = CatalogCharacter(
                    id=char_id,
                    name=(base.name if base else char_id.replace("_", " ").title()),
                    sport=(base.sport if base else "NBA"),
                    look=(base.look if base else ""),
                    default_wardrobe=(base.default_wardrobe if base else ""),
                    voice_style=(base.voice_style if base else "neutral, conversational"),
                    aliases=(base.aliases if base else []),
                    teams=(base.teams if base else []),
                    reference_images=(base.reference_images if base else []),
                    source=source,
                )
                db.add(row)
            for key in ("name", "sport", "look", "default_wardrobe", "voice_style",
                        "aliases", "teams", "reference_images", "active"):
                if key in fields and fields[key] is not None:
                    setattr(row, key, fields[key])
            if source == "admin":
                row.source = "admin"
            db.commit()
        finally:
            db.close()
        reload()
        return characters().get(char_id) or next(
            (c for c in _load_db_characters() if c.id == char_id), None
        )
    except Exception:  # noqa: BLE001 — persistence is a bonus, never a blocker
        log.exception("could not upsert catalog character %r", char_id)
        return None


def save_dynamic_character(member: CastMember, sport: str) -> Character | None:
    """Persist a researched off-catalog cast member into the DB layer.

    Called after web research confirmed WHO this is and wrote a real look and
    kit, so the entry meets the same bar as a curated one. Ronaldinho and
    Ronaldo stay separate people: the id comes from the member's own id/name,
    and an id already in the catalog is never overwritten here — curation
    wins over discovery. Returns the loaded Character (existing or new).
    Never raises.
    """
    from . import research
    if not research.looks_like_real_person(member.name):
        return None
    char_id = slugify(member.id or member.name)
    if not char_id:
        return None
    existing = characters().get(char_id)
    if existing:
        return existing
    saved = upsert_character(char_id, {
        "name": _clean(member.name, char_id.replace("_", " ").title()),
        "sport": _clean(sport, "NBA"),
        "look": _clean(member.look),
        "default_wardrobe": _clean(member.wardrobe),
        "voice_style": _clean(member.voice, "neutral, conversational"),
    }, source="auto-research")
    if saved:
        log.info("catalog: added dynamic character %r (%s)", saved.id, saved.name)
    return saved


def set_reference_images(char_id: str, reference_paths: list[str]) -> None:
    """Persist freshly generated stills: upload to Supabase Storage, record
    the storage keys on the character's DB row. Local files stay behind as
    the read cache. Never raises — an upload failure keeps the local-only
    paths so this job still benefits."""
    keys: list[str] = []
    try:
        from ..services import storage

        store = storage.get()
        for rel in reference_paths:
            local = CATALOG_DIR / rel
            if not local.exists():
                continue
            key = f"catalog/references/{local.name}"
            store.put(key, local, "image/jpeg")
            keys.append(key)
    except Exception:  # noqa: BLE001
        log.exception("could not upload references for %r; keeping local paths", char_id)
        keys = list(reference_paths)
    upsert_character(char_id, {"reference_images": keys or list(reference_paths)},
                     source="auto-research")


# -------------------------------------------------------------------- lookup

def all_characters() -> list[Character]:
    """Every entry incl. inactive, freshly loaded — the admin page's view."""
    reload()
    return sorted(_load_characters(), key=lambda c: (c.sport, c.id))


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
