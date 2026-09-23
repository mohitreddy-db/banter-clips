"""Story planning — the script step.

Three layers, tried in order, so this function always returns a usable plan:

1. Ask the language model for a structured plan.
2. Repair whatever came back: fill missing fields, force the scene count,
   enforce one-speaker-per-scene, trim over-long lines.
3. If the model is unreachable, unparseable, or unconfigured, build the plan
   from a deterministic template instead.

Layer 2 is the important one. Models return *nearly* right JSON far more often
than they return nothing, and rejecting a nearly-right plan wastes a call and
fails a job for no reason.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace

from . import catalog, library, prompts
from .defaults import ResolvedInput
from .types import WORDS_PER_SECOND, CastMember, Scene, VideoPlan, _clean

log = logging.getLogger("banter.video.planner")

BEATS = ("hook", "escalation", "payoff")


def build_plan(inp: ResolvedInput, client=None, storyline: str = "",
               rejected_note: str = "") -> VideoPlan:
    """Never raises. Always returns a plan with >= 2 scenes and a full cast.

    `storyline` is the Storyline Pack context block (real current squad,
    storylines, kit, places — see context.py). `rejected_note` carries the
    user's feedback when a previous script was rejected, so the rewrite is
    genuinely different."""
    roster = _ordered_roster(inp)
    venues = _venues(inp)

    raw: dict | None = None
    if client is not None and client.available:
        try:
            raw = _ask_model(inp, roster, venues, client,
                             storyline=storyline, rejected_note=rejected_note)
        except Exception:  # noqa: BLE001 — planning must never fail the job
            log.exception("planner call failed; falling back to template")

    if raw:
        plan = _from_raw(raw, inp, roster)
        plan.source = "llm"
    else:
        plan = _template(inp, roster, venues)
        plan.source = "fallback"

    plan = _repair(plan, inp, roster, venues)
    return _apply_team_identity(plan, inp)


# ------------------------------------------------------------ focus context

def _ordered_roster(inp: ResolvedInput) -> list[CastMember]:
    """The sport roster, with the take's focus at the front.

    Ordering matters twice: the template casts roster[0] as the subject, and
    the model reliably leans on whoever is listed first. Mentioned players
    lead, then the focused team's players, then everyone else.
    """
    roster = library.roster_for(inp.sport)
    focus = inp.focus
    team = focus.primary_team
    team_players = set(team.associated_players) if team else set()

    def rank(m: CastMember) -> int:
        if m.id in focus.player_ids:
            return 0
        if m.id in team_players:
            return 1
        char = catalog.get_character(m.id)
        if char and team and team.id in char.teams:
            return 1
        return 2

    return sorted(roster, key=rank)


def _venues(inp: ResolvedInput) -> list[str]:
    """Focused-team venues first, sport ambience after (plan §7.2)."""
    team = inp.focus.primary_team
    team_venues = list(team.venues) if team else []
    return team_venues + [v for v in library.venues_for(inp.sport) if v not in team_venues]


def _focus_note(inp: ResolvedInput) -> str:
    focus = inp.focus
    if focus.kind == "generic":
        return ""
    lines = [f"Focus: this take is {focus.kind}-focused."]
    for team_id in focus.team_ids:
        team = catalog.get_team(team_id)
        if team:
            lines.append(
                f"Team context: {team.name} — colour palette {team.palette()}; "
                f"dress their players in {team.wardrobe()}."
            )
    if focus.player_ids:
        lines.append("Centre the story on: " + ", ".join(focus.player_ids) + ".")
    return "\n".join(lines)


# ---------------------------------------------------------------- model call

def _ask_model(inp: ResolvedInput, roster, venues, client,
               storyline: str = "", rejected_note: str = "") -> dict | None:
    system = prompts.PLANNER_SYSTEM.format(
        scene_count=inp.scene_count,
        total_seconds=inp.seconds,
    )
    user = prompts.planner_user_message(
        inp.take, inp.sport, inp.tone, roster, venues,
        focus_note=_focus_note(inp), storyline=storyline,
        also_sports=inp.also_sports, subjects=inp.subjects, direction=inp.direction,
        has_reference=bool(getattr(inp, "has_reference", False)),
    )
    if rejected_note:
        user += (
            f"\nIMPORTANT — the user REJECTED a previous script for this take."
            f"\n{rejected_note}\nWrite a clearly different script: a different "
            f"situation and a different gag, not a rewording."
        )
    text = client.complete_json(system, user, max_tokens=6000)
    return _loads(text)


def _loads(text: str | None) -> dict | None:
    """Parse JSON that may be wrapped in prose or a code fence."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        brace = re.search(r"\{.*\}", text, re.S)  # last resort: first object in the blob
        if not brace:
            return None
        try:
            data = json.loads(brace.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


# ------------------------------------------------------------------ shaping

def _from_raw(raw: dict, inp: ResolvedInput, roster: list[CastMember]) -> VideoPlan:
    cast = [CastMember.from_raw(c, i) for i, c in enumerate(raw.get("cast") or [])]
    # Prefer the library's wording for anyone we recognise: it carries the
    # no-lettering wardrobe rule that keeps garbled text off the kit.
    cast = [_prefer_library(m, inp.sport) for m in cast]

    scenes_raw = raw.get("scenes") or []
    scenes = [
        Scene.from_raw(s, i, inp.venue)
        for i, s in enumerate(scenes_raw if isinstance(scenes_raw, list) else [])
    ]
    return VideoPlan(
        title=_clean(raw.get("title"), inp.take[:60]),
        take=inp.take,
        sport=inp.sport,
        tone=inp.tone,
        style=_clean(raw.get("style"), prompts.STYLE_BIBLE),
        cast=cast or list(roster[:2]),
        scenes=scenes,
    )


def _prefer_library(member: CastMember, sport: str) -> CastMember:
    known = library.resolve_member(member.id or member.name, sport)
    # resolve_member synthesises an entry for anyone off-roster; only override
    # when it actually matched something curated.
    on_roster = any(known.id == m.id for m in library.roster_for(sport))
    if not on_roster:
        return member
    # Identity (id, look, reference stills) comes from the library — but
    # wardrobe follows the STORY. This used to take the library entry whole,
    # which re-dressed a planner's "Ronaldo in an Arsenal home shirt" back
    # into his own club kit and made team stories visually incoherent.
    story_kit = _clean(member.wardrobe)
    if story_kit and story_kit.lower() != (known.wardrobe or "").lower():
        if "legible" not in story_kit.lower():
            story_kit += ", crisp legible lettering"
        return replace(known, wardrobe=story_kit)
    return known


def _template(inp: ResolvedInput, roster, venues) -> VideoPlan:
    """Deterministic plan. Not funny, but structurally correct and renderable."""
    cast = list(roster[: max(2, min(3, len(roster)))])
    subject = cast[0].name
    foil = cast[1].name if len(cast) > 1 else "everyone around him"
    seconds = round(inp.seconds / inp.scene_count, 1)

    beats = _beat_sequence(inp.scene_count)
    lines = {
        "hook": f"They really think {subject} is the problem.",
        "escalation": "It keeps getting worse.",
        "payoff": "Tell me I was wrong.",
    }
    actions = {
        "hook": f"{subject} stands still and stares straight down the lens while "
                f"{foil} gestures wildly behind him",
        "escalation": f"{subject} calmly walks past a scene of chaos without reacting",
        "payoff": f"{subject} turns to camera, raises an eyebrow, and holds the look",
    }
    scenes = []
    for i, beat in enumerate(beats):
        speaker = cast[i % len(cast)]
        scenes.append(Scene(
            index=i,
            beat=beat,
            venue=venues[i % len(venues)],
            action=(
                f"{inp.direction}. {actions.get(beat, actions['escalation'])}"
                if i == 0 and inp.direction else actions.get(beat, actions["escalation"])
            ),
            shot_size="full shot" if i % 2 == 0 else "wide shot",
            camera_angle="low angle" if i % 2 == 0 else "eye level",
            camera_move="slow push-in" if i % 2 == 0 else "locked-off static frame",
            lens="35mm, shallow depth of field",
            expression="deadpan, completely unbothered",
            lighting="hard overhead arena floodlights",
            sfx="crowd murmur and squeaking shoes",
            speaker_id=speaker.id,
            line=lines.get(beat, "Unbelievable."),
            delivery=speaker.voice,
            seconds=seconds,
        ))
    return VideoPlan(
        title=inp.take[:60],
        take=inp.take,
        sport=inp.sport,
        tone=inp.tone,
        style=prompts.STYLE_BIBLE,
        cast=cast,
        scenes=scenes,
    )


def _beat_sequence(count: int) -> list[str]:
    if count <= 1:
        return ["payoff"]
    if count == 2:
        return ["hook", "payoff"]
    return ["hook"] + ["escalation"] * (count - 2) + ["payoff"]


# ------------------------------------------------------------------- repair

def _repair(plan: VideoPlan, inp: ResolvedInput, roster, venues) -> VideoPlan:
    """Force the plan into something the renderer can definitely build."""
    if not plan.cast:
        plan.cast = list(roster[:2])
    plan.take = plan.take or inp.take
    plan.sport, plan.tone = inp.sport, inp.tone
    plan.style = plan.style or prompts.STYLE_BIBLE
    plan.title = plan.title or inp.take[:60]

    target = inp.scene_count
    scenes = [s for s in plan.scenes if isinstance(s, Scene)][:target]

    # Too few scenes: extend from the template rather than shipping a stub.
    if len(scenes) < target:
        filler = _template(inp, roster, venues).scenes
        for i in range(len(scenes), target):
            scenes.append(filler[i % len(filler)])
        if plan.source == "llm":
            plan.source = "repaired"

    beats = _beat_sequence(target)
    # Shots keep the lengths the model chose (long dialogue anchor, short
    # cutaways — the reference edit's rhythm), clamped to the generator's
    # reliable 2-10s window and scaled so the total hits the target.
    raw_secs = [min(10.0, max(2.0, float(s.seconds or 0) or inp.seconds / target))
                for s in scenes]
    scale = inp.seconds / sum(raw_secs) if raw_secs else 1.0
    cast_ids = [m.id for m in plan.cast]
    previous_speaker = ""

    for i, scene in enumerate(scenes):
        scene.index = i
        scene.beat = beats[i]
        scene.venue = scene.venue or venues[i % len(venues)]
        scene.action = scene.action or "the subject reacts to the camera"
        # Every camera axis gets a usable value: a model that omits one must
        # not leave the prompt with a dangling "Camera: , eye level, ,".
        scene.shot_size = scene.shot_size or "full shot"
        scene.camera_angle = scene.camera_angle or "eye level"
        scene.camera_move = scene.camera_move or "slow push-in"
        scene.lens = scene.lens or "35mm, shallow depth of field"
        scene.seconds = round(raw_secs[i] * scale, 1)

        # Speaker must exist, and must differ from the previous scene so that
        # cross-clip voice drift never lands on the same character twice.
        if scene.speaker_id not in cast_ids:
            resolved = library.resolve_member(scene.speaker_id, inp.sport, i)
            if resolved.id not in cast_ids and len(plan.cast) < 3:
                plan.cast.append(resolved)
                cast_ids.append(resolved.id)
            scene.speaker_id = resolved.id if resolved.id in cast_ids else cast_ids[i % len(cast_ids)]
        if scene.speaker_id == previous_speaker and len(cast_ids) > 1:
            alternatives = [c for c in cast_ids if c != previous_speaker]
            scene.speaker_id = alternatives[i % len(alternatives)]
        previous_speaker = scene.speaker_id

        # Silent cutaways are allowed — a wordless reaction is a real shot.
        scene.line = scene.trimmed_line() if scene.line else ""
        if not scene.delivery:
            speaker = plan.speaker_for(scene)
            scene.delivery = speaker.voice if speaker else "deadpan"

    # But a fully silent video is a bug, not a style: guarantee one line.
    if scenes and not any(s.line for s in scenes):
        scenes[0].line = "Unbelievable."

    # ONE WORLD (the reference edit's defining trait): every shot happens in
    # the same place, so every shot carries the same venue text verbatim.
    world = next((s.venue for s in scenes if s.venue), venues[0] if venues else "")
    for scene in scenes:
        scene.venue = world

    plan.scenes = scenes
    return plan


def _apply_team_identity(plan: VideoPlan, inp: ResolvedInput) -> VideoPlan:
    """Stamp the detected focus onto the plan (plan §7.2).

    Cast members who belong to a focused team get that team's kit, so a
    Lakers take renders everyone in purple and gold regardless of what the
    model or the character's default entry said. Our deterministic detection
    wins over whatever `focus` the model returned — the model's value is
    advisory and unvalidated.
    """
    focus = inp.focus
    plan.focus = focus.kind
    plan.team_ids = list(focus.team_ids)
    if not focus.team_ids:
        return plan

    focus_teams = [t for t in (catalog.get_team(tid) for tid in focus.team_ids) if t]
    for member in plan.cast:
        char = catalog.get_character(member.id)
        if not char:
            continue
        for team in focus_teams:
            if team.id in char.teams:
                member.wardrobe = team.wardrobe()
                break
    return plan
