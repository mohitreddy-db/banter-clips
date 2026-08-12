"""Prompt construction.

Two rules here were learned from real renders, not from documentation:

1. Name the person. Removing the name to suppress text also removes the
   likeness — a named star renders accurately without any reference image.
2. State the no-lettering rule positively on the wardrobe ("a plain kit with
   no lettering"), not only as a trailing negative. Trailing negatives alone
   produced garbled shirt text and leaked brand boards in every early render.

Neither rule is sufficient alone; both go in every prompt.
"""

from __future__ import annotations

import re

from .types import Scene, VideoPlan

STYLE_BIBLE = (
    "Cinematic photoreal sports comedy, modern 35mm film look, shallow depth of field, "
    "bright broadcast lighting, vertical 9:16 composition, obvious visual comedy, "
    "highly detailed faces and fabric texture"
)

# Appended to every image and motion prompt.
NEGATIVES = (
    "Absolutely no on-screen captions, subtitles, watermarks, brand logos, "
    "advertising boards, signage, scoreboards, crests, wordmarks, or readable text "
    "anywhere in the frame. No team logos. No collages or multi-panel layouts"
)

# Stills only. A camera direction like "wide shot, then a close-up" describes a
# sequence, and an image model renders a sequence as stacked panels — which is
# exactly how a keyframe came back as a three-panel collage. Say "one frame".
SINGLE_FRAME = (
    "This is ONE single continuous photograph from ONE camera position: "
    "no split screen, no collage, no panels, no grid, no storyboard, "
    "no before-and-after, no multiple shots in the same image"
)

# A shot list joined by any of these is two shots, not one.
_SHOT_SPLIT = re.compile(
    r"\s*(?:,\s*)?\b(?:then|followed by|cut(?:ting)? to|next|after that|and then)\b\s*",
    re.IGNORECASE,
)

TONE_DIRECTION = {
    "Funny": "warm absurdist physical comedy; nobody is humiliated",
    "Savage": "sharp, cocky mockery aimed at the situation rather than at a person's dignity",
    "Hype": "triumphant, loud, celebratory energy",
    "Bold": "confident, declarative, unbothered swagger",
}


def style_for(plan: VideoPlan) -> str:
    tone = TONE_DIRECTION.get(plan.tone, TONE_DIRECTION["Bold"])
    return f"{plan.style or STYLE_BIBLE}. Tone: {tone}"


def cast_clause(plan: VideoPlan, scene: Scene) -> str:
    """Describe whoever should be visible, name first, wardrobe rule attached."""
    speaker = plan.speaker_for(scene)
    members = [speaker] if speaker else []
    for member in plan.cast:
        if member not in members and len(members) < 3:
            members.append(member)
    if not members:
        return "a professional athlete in plain team-coloured kit with no lettering"
    return "; ".join(f"{m.name}, {m.look}, wearing {m.wardrobe}" for m in members if m)


def first_shot(camera: str) -> str:
    """Keep only the opening framing from a multi-shot camera direction."""
    head = _SHOT_SPLIT.split(str(camera or ""), maxsplit=1)[0].strip(" .,;")
    return head or "medium wide shot, eye level"


def build_image_prompt(plan: VideoPlan, scene: Scene) -> str:
    """The keyframe. One frame, one camera position — no motion, no dialogue."""
    return (
        f"{style_for(plan)}. "
        f"{SINGLE_FRAME}. "
        f"Setting: {scene.venue}. "
        f"Subjects: {cast_clause(plan, scene)}. "
        f"Action: {scene.action}. "
        f"Framing: {first_shot(scene.camera)}. "
        f"Keep the lower quarter of the frame visually calm. "
        f"{NEGATIVES}."
    )


def build_motion_prompt(plan: VideoPlan, scene: Scene) -> str:
    """The animation. Describes only what moves, plus the spoken line.

    The generator performs the dialogue itself and lip-syncs it, so the line
    goes in the prompt rather than through a separate speech step.
    """
    speaker = plan.speaker_for(scene)
    parts = [
        f"{style_for(plan)}. ",
        f"Action: {scene.action}. ",
        f"Camera: {scene.camera}. ",
    ]
    line = scene.trimmed_line()
    if line and speaker:
        parts.append(
            f'Dialogue: {speaker.name}, {scene.delivery or speaker.voice}, says "{line}". '
        )
    elif line:
        parts.append(f'Dialogue: a voice says "{line}". ')
    parts.append("Audio: ambient crowd noise under the dialogue. ")
    parts.append(f"{NEGATIVES}.")
    return "".join(parts)


PLANNER_SYSTEM = """\
You write short vertical sports-comedy videos. You turn one opinion into a
scene-by-scene plan.

Hard rules:
- Keep the user's stance. Sharpen it, exaggerate it, never reverse it.
- Exactly {scene_count} scenes, structured hook -> escalation -> payoff.
  Each escalation must RAISE the premise, never restate it.
- Each scene has AT MOST ONE speaker, and consecutive scenes must use
  DIFFERENT speakers. This is a hard technical constraint, not a style note.
- A line must be speakable inside its scene: at most {max_words} words.
- Cast only from the provided roster. Use their exact `id` values.
- When the take targets a team, prefer players who belong to that team and
  use the team's colour palette and venues. Still never invent logos,
  crests, or any readable text on clothing or signage.
- Comedy comes from a visual situation, not from wordplay. Describe what the
  camera literally sees.
- Never invent a factual result, score, or quote presented as real news.
- `camera` describes ONE camera position only — a single framing such as
  "low-angle medium shot" or "slow push-in on his face". Never a shot list:
  no "then", no "cut to", no "wide shot followed by a close-up". A scene is
  one continuous take.
- `style` describes ONLY look and lighting — lens, grade, mood. Never camera
  movement, editing or transitions.

Return ONLY JSON:
{{"title": "...",
  "style": "one line of art direction",
  "focus": "player|team|matchup|generic",
  "teams": ["team ids the video leans on, may be empty"],
  "cast": [{{"id": "...", "name": "...", "look": "...", "wardrobe": "...", "voice": "..."}}],
  "scenes": [{{"beat": "hook|escalation|payoff", "venue": "...", "action": "...",
              "camera": "...", "speaker_id": "...", "line": "...",
              "delivery": "...", "seconds": {scene_seconds}}}]}}"""


def planner_user_message(
    take: str, sport: str, tone: str, roster: list, venues: list,
    focus_note: str = "",
) -> str:
    names = "\n".join(f"  - id={m.id!r} name={m.name!r} ({m.look})" for m in roster)
    places = "\n".join(f"  - {v}" for v in venues)
    context = f"\n{focus_note}\n" if focus_note else ""
    return (
        f"Sport: {sport}\n"
        f"Tone: {tone}\n"
        f"The opinion to dramatise: {take}\n"
        f"{context}\n"
        f"Roster you may cast (use these ids):\n{names}\n\n"
        f"Locations you may reuse:\n{places}\n"
    )


# One reference still per view, generated by catalog_build with the SAME image
# model that renders scene keyframes (plan §5.6): neutral studio conditions so
# the reference carries identity, not scene context.
REFERENCE_STILL_PROMPT = (
    "Professional studio reference photograph, neutral soft lighting, plain "
    "seamless light-grey background, vertical 9:16 composition. "
    "Subject: {name}, {look}, wearing {wardrobe}, with plain unbranded "
    "single-colour shoes. "
    "{framing}. Neutral relaxed expression, arms at sides. "
    "Extremely high facial and body detail. " + SINGLE_FRAME + ". " + NEGATIVES + "."
)

REFERENCE_VIEWS = {
    "face": "Tight head-and-shoulders close-up, face perfectly sharp and centred",
    "full": "Full-body shot from head to feet, whole figure visible and centred",
}
