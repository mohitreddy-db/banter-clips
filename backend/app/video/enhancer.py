"""Prompt enhancement — turn a rough take into a brief worth spending money on.

Everything downstream is only as good as what arrives here. A vague take
("lakers bad") gives the planner nothing visual to work with; an off-catalog
name renders as a generic stand-in; an ambiguous team reference paints an
entire video in the wrong palette. Those failures are cheap to prevent here
and expensive to discover after $2.40 of animation.

Two jobs:

1. **Sharpen** the take (one LLM call): keep the stance, make it specific,
   visual and speakable. Also extract who and what it is really about.
2. **Ask** about the gaps that measurably change output quality — and only
   those. Every question carries a default, so silence is always a valid
   answer.

Hard contract, same as the rest of the pipeline: never raises, never blocks.
With no LLM, no answers and no catalog, `enhance()` still returns a complete
Brief that generation can run on.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field

from . import catalog, defaults, focus as focus_mod
from .types import _clean

log = logging.getLogger("banter.video.enhancer")

# Fixed art directions. The planner used to invent a style line per job, which
# is how one video ended up half photoreal and half cartoon — free-form style
# text is not repeatable. These are the only styles the pipeline offers, and
# every one of them is a photographic look; they differ in grade, not medium.
STYLE_PRESETS: dict[str, dict[str, str]] = {
    "broadcast": {
        "label": "Broadcast real",
        "detail": "Bright and clean, like a live broadcast.",
        "style": "crisp broadcast lighting, neutral colour grade, deep clarity",
    },
    "cinematic": {
        "label": "Golden-hour cinematic",
        "detail": "Warm and filmic. Great for big moments.",
        "style": "warm golden-hour light, soft haze, rich filmic grade, long lens",
    },
    "gritty": {
        "label": "Gritty documentary",
        "detail": "Raw and hand-held. Suits a brutal take.",
        "style": "hand-held documentary framing, hard tungsten light, "
                 "desaturated grade, visible grain",
    },
}
DEFAULT_STYLE = "broadcast"

# Takes shorter than this cannot carry a story; below it we ask rather than
# silently substituting a generic opinion.
VAGUE_TAKE_CHARS = 25


@dataclass
class Option:
    value: str
    label: str
    detail: str = ""


@dataclass
class Question:
    """One thing worth asking. Always answerable by doing nothing."""

    id: str
    prompt: str
    why: str                      # what changes in the output if answered
    options: list[Option] = field(default_factory=list)
    kind: str = "choice"          # "choice" | "text"
    default: str = ""
    required: bool = False        # advisory only; nothing is ever blocked

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Brief:
    """A complete, renderable brief plus whatever is still worth asking."""

    take: str                      # what generation will actually use
    original_take: str = ""
    sport: str = "NBA"
    tone: str = "Bold"
    seconds: int = 15
    style_id: str = DEFAULT_STYLE
    style: str = ""
    cast_ids: list[str] = field(default_factory=list)
    team_ids: list[str] = field(default_factory=list)
    # Display names for the ids above. Nothing user-facing should ever render
    # an id — "wembanyama" and "inter-miami" are our vocabulary, not theirs.
    cast_names: list[str] = field(default_factory=list)
    team_names: list[str] = field(default_factory=list)
    style_label: str = ""
    unknown_names: list[str] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    source: str = "fallback"       # "llm" | "fallback"

    @property
    def needs_input(self) -> bool:
        return bool(self.questions)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["questions"] = [q.to_dict() for q in self.questions]
        return data


# ------------------------------------------------------------------ the call

ENHANCER_SYSTEM = """\
You prepare one-line sports opinions for a short comedy video generator.

Rewrite the take so it is:
- the SAME opinion, never reversed, never softened
- specific and concrete rather than abstract ("the Lakers are frauds" beats
  "the Lakers are bad")
- naturally spoken, under 200 characters
- about something a camera could show happening

Then identify what it is really about.

Return ONLY JSON:
{"take": "the sharpened take",
 "subjects": ["proper names of people mentioned or clearly implied"],
 "teams": ["proper names of teams mentioned or clearly implied"],
 "sport": "NBA|NFL|Soccer|MLB|unknown",
 "is_vague": true/false,
 "ambiguity": "what a human would need to clarify, or empty string",
 "suggested_tone": "Funny|Savage|Hype|Bold"}

is_vague is true when the take is too thin to build three escalating comedy
beats from — a bare insult, a single word, or an opinion with no situation in
it. ambiguity is for genuine forks ("City" could be Man City or a US city),
not for stylistic preference."""


def enhance(
    take: object = None,
    sport: object = None,
    tone: object = None,
    seconds: object = None,
    *,
    answers: dict | None = None,
    client=None,
) -> Brief:
    """Sharpen the take and work out what is still worth asking. Never raises.

    `answers` maps question id -> chosen value, from a previous round. Passing
    them back suppresses those questions and applies the choices.
    """
    answers = {k: _clean(v) for k, v in (answers or {}).items() if _clean(v)}
    original = _clean(take)

    raw: dict | None = None
    if client is not None and getattr(client, "available", False) and original:
        try:
            raw = _ask(original, client)
        except Exception:  # noqa: BLE001 — enhancement is never load-bearing
            log.exception("enhancer call failed; using the take as written")

    sharpened = _clean((raw or {}).get("take")) or original
    # A model that "sharpens" a take into something twice as long has usually
    # editorialised rather than sharpened; keep the user's own words instead.
    if original and len(sharpened) > max(280, len(original) * 2):
        sharpened = original
        (raw or {}).pop("take", None)

    brief = Brief(
        take=answers.get("take") or sharpened or original,
        original_take=original,
        source="llm" if raw else "fallback",
    )

    # Resolve everything through the normal path so the brief and the eventual
    # run agree on sport, tone, duration and scene count.
    resolved = defaults.resolve(
        brief.take,
        answers.get("sport") or sport or _clean((raw or {}).get("sport")),
        answers.get("tone") or tone or _clean((raw or {}).get("suggested_tone")),
        answers.get("seconds") or seconds,
    )
    # An empty or too-short take became a usable one during resolution; the
    # brief must carry what will actually be rendered, not the empty string.
    brief.take = brief.take or resolved.take
    brief.sport, brief.tone, brief.seconds = resolved.sport, resolved.tone, resolved.seconds
    brief.cast_ids = list(resolved.focus.player_ids)
    brief.team_ids = list(resolved.focus.team_ids)

    style_id = answers.get("style") if answers.get("style") in STYLE_PRESETS else None
    brief.style_id = style_id or _style_for_tone(brief.tone)
    brief.style = STYLE_PRESETS[brief.style_id]["style"]
    brief.style_label = STYLE_PRESETS[brief.style_id]["label"]

    brief.cast_names = [
        (catalog.get_character(cid).name if catalog.get_character(cid) else cid)
        for cid in brief.cast_ids
    ]
    brief.team_names = [
        (catalog.get_team(tid).name if catalog.get_team(tid) else tid)
        for tid in brief.team_ids
    ]

    brief.unknown_names = _unknown_names(raw, brief)
    brief.questions = _questions(brief, raw, resolved, answers,
                                 explicit_sport=sport, explicit_tone=tone,
                                 explicit_seconds=seconds)
    return brief


def _ask(take: str, client) -> dict | None:
    text = client.complete_json(ENHANCER_SYSTEM, f"The take: {take}")
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


# ------------------------------------------------------------------ analysis

def _style_for_tone(tone: str) -> str:
    """A sensible default look per tone, still overridable by the user."""
    return {"Savage": "gritty", "Hype": "cinematic", "Funny": "broadcast"}.get(
        tone, DEFAULT_STYLE
    )


def _unknown_names(raw: dict | None, brief: Brief) -> list[str]:
    """Named people the catalog cannot render as themselves.

    A name that resolves to a *team* is not unknown cast — the team supplies
    its own players — so both halves of the catalog are consulted before
    telling the user we do not know someone.
    """
    subjects = [_clean(s) for s in ((raw or {}).get("subjects") or []) if _clean(s)]
    known_teams = {t.lower() for t in brief.team_ids}
    unknown: list[str] = []
    for name in subjects[:6]:
        chars, teams = catalog.find_mentions(name)
        if chars or teams or name.lower() in known_teams:
            continue
        if name.lower() not in {u.lower() for u in unknown}:
            unknown.append(name)
    return unknown


def _questions(
    brief: Brief, raw: dict | None, resolved, answers: dict,
    explicit_sport, explicit_tone, explicit_seconds,
) -> list[Question]:
    """Only gaps that measurably change the output. Every one has a default."""
    questions: list[Question] = []
    asked = set(answers)

    # 1. A take too thin to build beats from. Worth asking before anything else.
    vague = bool((raw or {}).get("is_vague")) or len(brief.take) < VAGUE_TAKE_CHARS
    if vague and "take" not in asked:
        questions.append(Question(
            id="take",
            kind="text",
            prompt="Say a bit more — what happened, and who looks bad?",
            why="The more specific you are, the funnier it lands.",
            default=brief.take,
            required=True,
        ))

    # 2. A genuine fork the model could not resolve on its own.
    ambiguity = _clean((raw or {}).get("ambiguity"))
    if ambiguity and "clarify" not in asked:
        questions.append(Question(
            id="clarify",
            kind="text",
            prompt=f"Quick check: {ambiguity}",
            why="So we point the joke at the right person.",
            default="",
        ))

    # 3. Names we cannot render well. Offer the honest choices.
    if brief.unknown_names and "cast" not in asked:
        names = ", ".join(brief.unknown_names[:3])
        options = [
            Option("proceed", "Use them anyway",
                   "We'll do our best — the resemblance may be loose."),
            Option("research", "Look them up first",
                   "Takes a moment longer, usually looks better."),
        ]
        for member in _catalog_suggestions(brief.sport):
            options.append(Option(f"swap:{member.id}", f"Use {member.name} instead",
                                  "We nail this one every time."))
        questions.append(Question(
            id="cast",
            prompt=f"We don't know {names} well yet. How do you want to play it?",
            why="Some faces we get spot on; others come out as a lookalike.",
            options=options[:4],
            default="proceed",
        ))

    # 4. Ambiguous team focus: two teams, no clear lead.
    if len(brief.team_ids) > 1 and "team" not in asked:
        options = []
        for team_id in brief.team_ids[:3]:
            team = catalog.get_team(team_id)
            if team:
                options.append(Option(team.id, team.name,
                                      f"{team.palette()} kit, on their turf"))
        options.append(Option("both", "Both, evenly",
                              "Share the screen time."))
        if len(options) > 1:
            questions.append(Question(
                id="team",
                prompt="Whose side are we on?",
                why="Sets the kit colours and where it's filmed.",
                options=options,
                default="both",
            ))

    # 5. Preferences the user may simply not have stated. Asked last, never
    #    when they were passed explicitly.
    if not _clean(explicit_tone) and "tone" not in asked:
        questions.append(Question(
            id="tone",
            prompt="How should it hit?",
            why="Changes how the characters talk.",
            options=[Option(t, t, d) for t, d in _TONE_BLURBS.items()],
            default=brief.tone,
        ))
    if "style" not in asked:
        questions.append(Question(
            id="style",
            prompt="What should it look like?",
            why="Sets the mood and lighting throughout.",
            options=[Option(k, v["label"], v["detail"]) for k, v in STYLE_PRESETS.items()],
            default=brief.style_id,
        ))
    if not _clean(explicit_seconds) and "seconds" not in asked:
        questions.append(Question(
            id="seconds",
            prompt="How long?",
            why="Longer gives the joke more room to build.",
            options=[
                Option("15", "15 seconds", "Quick hit, 2 scenes"),
                Option("30", "30 seconds", "Room to build, 4 scenes"),
                Option("60", "60 seconds", "Full sketch, 8 scenes"),
            ],
            default=str(brief.seconds),
        ))
    return questions


_TONE_BLURBS = {
    "Funny": "warm, absurd, nobody gets hurt",
    "Savage": "sharp mockery of the situation",
    "Hype": "loud and celebratory",
    "Bold": "confident, declarative swagger",
}


def _catalog_suggestions(sport: str) -> list:
    """Catalogued characters with reference stills — our best-rendering cast."""
    best = [c for c in catalog.characters_for(sport) if c.reference_paths()]
    return best[:2]


# --------------------------------------------------------------- application

def apply_answers(brief: Brief, answers: dict) -> Brief:
    """Fold a round of answers back into the brief. Re-runs the analysis."""
    merged = {}
    for question in brief.questions:
        if question.default:
            merged[question.id] = question.default
    merged.update({k: _clean(v) for k, v in (answers or {}).items() if _clean(v)})
    return enhance(
        brief.original_take or brief.take,
        merged.get("sport") or brief.sport,
        merged.get("tone") or brief.tone,
        merged.get("seconds") or brief.seconds,
        answers=merged,
        client=None,   # the take is already sharpened; do not re-spend
    )


def resolved_from(brief: Brief) -> defaults.ResolvedInput:
    """The brief as the ResolvedInput the planner consumes.

    Cast and team choices made by the user override what detection found, so
    an answered question actually changes the render.
    """
    resolved = defaults.resolve(brief.take, brief.sport, brief.tone, brief.seconds)
    if brief.team_ids:
        resolved.focus = focus_mod.Focus(
            kind=resolved.focus.kind,
            player_ids=list(brief.cast_ids),
            team_ids=list(brief.team_ids),
        )
        team = resolved.focus.primary_team
        if team and team.venues:
            resolved.venue = team.venues[0]
    return resolved
