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

from . import catalog, library, prompts
from .defaults import ResolvedInput
from .types import WORDS_PER_SECOND, CastMember, Scene, VideoPlan, _clean

log = logging.getLogger("banter.video.planner")

BEATS = ("hook", "escalation", "payoff")


def build_plan(inp: ResolvedInput, client=None) -> VideoPlan:
    """Never raises. Always returns a plan with >= 2 scenes and a full cast."""
    roster = _ordered_roster(inp)
    venues = _venues(inp)

    raw: dict | None = None
    if client is not None and client.available:
        try:
            raw = _ask_model(inp, roster, venues, client)
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

def _ask_model(inp: ResolvedInput, roster, venues, client) -> dict | None:
    scene_seconds = round(inp.seconds / inp.scene_count, 1)
    system = prompts.PLANNER_SYSTEM.format(
        scene_count=inp.scene_count,
        max_words=int(scene_seconds * WORDS_PER_SECOND),
        scene_seconds=scene_seconds,
    )
    user = prompts.planner_user_message(
        inp.take, inp.sport, inp.tone, roster, venues, focus_note=_focus_note(inp)
    )
    text = client.complete_json(system, user)
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
    return known if on_roster else member


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
            action=actions.get(beat, actions["escalation"]),
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
    per_scene = round(inp.seconds / target, 1)
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
        scene.seconds = per_scene

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

        if not scene.line:
            scene.line = "Unbelievable."
        scene.line = scene.trimmed_line()
        if not scene.delivery:
            speaker = plan.speaker_for(scene)
            scene.delivery = speaker.voice if speaker else "deadpan"

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
