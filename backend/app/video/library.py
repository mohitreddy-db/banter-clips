"""Cast and venue library.

Two jobs:

1. Give the planner a roster it is allowed to cast from, so the take alone
   cannot conjure an arbitrary person.
2. Never fail. An unknown name still yields a usable CastMember built from the
   name itself, so a plan referencing someone off-roster still renders.

The roster is sourced from the JSON catalog (`catalog.py`, plan §5); the
hard-coded ROSTER below is the fallback when the catalog is missing or
unreadable, so a broken data file can never take generation down.

Every entry names the person (that is what holds the likeness) and pairs it
with the AUTHENTIC kit, asked for by name and number. Measured: asking for
the real kit renders clean lettering; banning lettering renders gibberish.
"""

from __future__ import annotations

import re

from . import catalog
from .types import CastMember

_KIT = "with the club crest, name and number in crisp legible lettering"

# Deliberately small and reviewable. Add entries only after seeing a render.
ROSTER: dict[str, list[dict]] = {
    "NBA": [
        {"id": "wembanyama", "name": "Victor Wembanyama",
         "look": "an extremely tall and very slim 7-foot-4 French basketball player "
                 "with very long limbs and short dark hair, towering over everyone",
         "wardrobe": f"a plain black and silver basketball uniform {_KIT}",
         "voice": "calm, French-accented, understated"},
        {"id": "brunson", "name": "Jalen Brunson",
         "look": "a short stocky 6-foot-2 point guard with a thick dark beard",
         "wardrobe": f"a plain blue and orange basketball uniform {_KIT}",
         "voice": "warm, confident, quick"},
        {"id": "coach", "name": "a weary head coach",
         "look": "a tired middle-aged head coach holding a clipboard",
         "wardrobe": "a plain grey polo shirt and dark trousers",
         "voice": "flat, exhausted, deadpan"},
        {"id": "reporter", "name": "a courtside reporter",
         "look": "a neatly dressed courtside reporter holding a microphone",
         "wardrobe": "a plain dark blazer",
         "voice": "bright, professional"},
    ],
    "Soccer": [
        {"id": "messi", "name": "Lionel Messi",
         "look": "a short left-footed forward with a short beard and dark hair",
         "wardrobe": f"a plain blue and white striped football kit {_KIT}",
         "voice": "quiet, deadpan"},
        {"id": "official", "name": "a senior football official",
         "look": "a bald football administrator in a dark suit",
         "wardrobe": "a plain dark navy suit and tie",
         "voice": "smug, self-important"},
        {"id": "referee", "name": "a match referee",
         "look": "a stern referee holding cards",
         "wardrobe": "a plain black referee kit",
         "voice": "clipped, authoritative"},
    ],
    "NFL": [
        {"id": "quarterback", "name": "a veteran star quarterback",
         "look": "a tall athletic quarterback in full pads and helmet under one arm",
         "wardrobe": f"a plain dark football uniform {_KIT}",
         "voice": "gravelly, assured"},
        {"id": "lineman", "name": "an enormous offensive lineman",
         "look": "an extremely large and wide offensive lineman",
         "wardrobe": f"a plain football uniform {_KIT}",
         "voice": "booming, cheerful"},
        {"id": "coach", "name": "a weary head coach",
         "look": "a tired head coach in a team cap with a headset",
         "wardrobe": "a plain team-coloured pullover",
         "voice": "flat, exhausted, deadpan"},
    ],
    "MLB": [
        {"id": "slugger", "name": "a star power hitter",
         "look": "a broad-shouldered baseball slugger with a thick beard",
         "wardrobe": f"a plain pinstriped baseball uniform {_KIT}",
         "voice": "laconic, dry"},
        {"id": "pitcher", "name": "an ace relief pitcher",
         "look": "a lean pitcher mid-windup",
         "wardrobe": f"a plain baseball uniform {_KIT}",
         "voice": "intense, clipped"},
        {"id": "umpire", "name": "a home plate umpire",
         "look": "a stocky umpire in a chest protector and mask",
         "wardrobe": "plain dark umpire gear",
         "voice": "bellowing, theatrical"},
    ],
}

VENUES: dict[str, list[str]] = {
    "NBA": [
        "a packed basketball arena at night, bright broadcast lighting, blurred crowd",
        "the courtside team bench of a packed basketball arena",
        "a quiet locker room with wooden lockers and low lighting",
        "the arena floor during a championship celebration with confetti falling",
    ],
    "Soccer": [
        "a floodlit football stadium pitch at night, blurred crowd behind",
        "a concrete stadium tunnel lit by strip lights",
        "a video review room full of monitors",
        "a stadium pitch at full time with confetti and streamers",
    ],
    "NFL": [
        "a packed football stadium at night under floodlights",
        "the sideline of a football field, benches and equipment behind",
        "a fluorescent-lit locker room",
        "a football field covered in confetti after a title game",
    ],
    "MLB": [
        "a floodlit baseball stadium at night, blurred crowd",
        "a dugout lined with bats and helmets",
        "the pitcher's mound in an empty stadium at dusk",
        "an infield covered in celebration confetti",
    ],
    # The sports added on 2026-08-31. Without these every one of them fell
    # through to the NBA list, so a Formula 1 take was staged in a basketball
    # arena — the exact wrong-world failure the venue list exists to prevent.
    "NHL": [
        "a packed ice hockey arena at night, bright broadcast lighting, blurred crowd",
        "the players' bench beside the boards, sticks racked behind",
        "a concrete tunnel to the ice, skate guards on the floor",
        "the ice at full time, streamers and hats scattered across it",
    ],
    "Tennis": [
        "a floodlit tennis show court at night, blurred crowd in the stands",
        "the players' chairs at the net post, towels and racket bags beside them",
        "a practice court in bright daylight, ball baskets at the baseline",
        "centre court after match point, the winner's bag by the umpire's chair",
    ],
    "F1": [
        "a Formula 1 pit lane, garages and tyre stacks under bright light",
        "the starting grid before lights out, mechanics crouched by the cars",
        "a team garage full of monitors and engineers in headsets",
        "the podium above the pit straight, confetti in the air",
    ],
    "Cricket": [
        "a floodlit cricket ground at night, the square lit white, blurred crowd",
        "the players' balcony above the pavilion, kit bags and helmets around",
        "a practice net beside the outfield in hard afternoon sun",
        "the middle at the close of play, stumps pulled and shadows long",
    ],
    "Golf": [
        "a championship golf course fairway in soft morning light, galleries roped off",
        "the eighteenth green with a leaderboard behind and spectators standing",
        "a driving range at sunrise, buckets of balls lined up",
        "the clubhouse terrace overlooking the closing hole",
    ],
    "Boxing": [
        "a boxing ring under hard overhead lights, dark arena crowd beyond the ropes",
        "the walkout tunnel filled with haze and phone lights",
        "a corner between rounds, stool out and towels over the ropes",
        "a weigh-in stage with sponsor boards and photographers at the front",
    ],
    "MMA": [
        "the octagon under hard overhead lights, dark arena crowd beyond the cage",
        "the walkout tunnel filled with haze and phone lights",
        "a cage corner between rounds, cutman working with the stool out",
        "a press-conference face-off stage with sponsor boards behind",
    ],
    # "Other" keeps a take about darts, chess boxing or anything else out of
    # a basketball arena: neutral enough to host any sport's story.
    "Other": [
        "a packed indoor arena at night, bright broadcast lighting, blurred crowd",
        "a competitor's bench at the edge of the arena floor",
        "a plain locker room with benches and kit bags",
        "an arena floor after the final, confetti settling",
    ],
}

_GENERIC_VENUE = "a packed stadium at night, bright broadcast lighting, blurred crowd"

# Nicknames the crowd actually uses. Needed because a nickname is often not a
# prefix of the name — "wemby" diverges from "wembanyama" at the fifth letter,
# so no amount of prefix matching finds it.
ALIASES: dict[str, str] = {
    "wemby": "wembanyama",
    "the alien": "wembanyama",
    "jb": "brunson",
    "captain clutch": "brunson",
    "the goat": "messi",
    "leo": "messi",
    "la pulga": "messi",
    "gaffer": "coach",
    "the ref": "referee",
    "ump": "umpire",
    "qb": "quarterback",
}


def roster_for(sport: str) -> list[CastMember]:
    """Catalog characters for the sport; hard-coded fallback if catalog is empty."""
    from_catalog = [catalog.cast_member(c) for c in catalog.characters_for(sport)]
    if from_catalog:
        return from_catalog
    entries = ROSTER.get(sport) or ROSTER["NBA"]
    return [CastMember(**e) for e in entries]


def venues_for(sport: str) -> list[str]:
    return VENUES.get(sport) or VENUES.get("NBA") or [_GENERIC_VENUE]


def default_venue(sport: str) -> str:
    return venues_for(sport)[0]


def resolve_member(name_or_id: str, sport: str, index: int = 0) -> CastMember:
    """Best-effort lookup. Never returns None.

    Matches on id or name, case- and punctuation-insensitively, then on any
    shared word (so "Wemby" finds "Victor Wembanyama"). Falls back to a member
    synthesised from the requested name, which keeps an off-roster plan
    renderable instead of dropping the character.
    """
    wanted = _norm(name_or_id)
    if not wanted:
        pool = roster_for(sport)
        return pool[index % len(pool)]

    pool = roster_for(sport)
    for member in pool:
        if wanted in (_norm(member.id), _norm(member.name)):
            return member

    # Catalog aliases first ("wemby", "cr7"), then the built-in nickname map.
    for char in catalog.characters_for(sport):
        if wanted in (_norm(a) for a in char.aliases):
            for member in pool:
                if member.id == char.id:
                    return member

    aliased = ALIASES.get(wanted)
    if aliased:
        for member in pool:
            if member.id == aliased or member.id.startswith(f"{aliased}_"):
                return member

    for member in pool:
        if _overlap(wanted, _norm(member.name)) or _overlap(wanted, _norm(member.id)):
            return member
    # Off-roster: build something usable rather than failing the job.
    return CastMember(
        id=re.sub(r"[^a-z0-9]+", "_", wanted).strip("_")[:40] or f"cast_{index}",
        name=name_or_id.strip()[:80],
        look=f"{name_or_id.strip()[:80]}, a professional {sport} figure",
        wardrobe=f"plain team-coloured kit {_KIT}",
        voice="neutral, conversational",
    )


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", str(value or "").lower()).strip()


def _overlap(a: str, b: str) -> bool:
    """True when two names plausibly refer to the same person.

    Word equality, or a near-misspelling of a word. This used to be a shared
    4-character prefix, which is how "Ronaldinho" would have resolved to
    Ronaldo ("rona" == "rona") — DIFFERENT people must never merge. Edit
    distance keeps the misspelling tolerance ("wembenyama" → "wembanyama",
    one edit) while a genuinely different name ("ronaldinho", three inserts
    away from "ronaldo") stays itself.
    """
    aw = {w for w in a.split() if len(w) > 3}
    bw = {w for w in b.split() if len(w) > 3}
    if aw & bw:
        return True
    return any(_near_misspelling(x, y) for x in aw for y in bw)


def _near_misspelling(a: str, b: str) -> bool:
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 5:
        return False
    return _edit_distance(a, b) <= 1


def _edit_distance(a: str, b: str) -> int:
    """Plain Levenshtein; names are short, so O(len*len) is nothing."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        row = [i]
        for j, cb in enumerate(b, 1):
            row.append(min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = row
    return prev[-1]
