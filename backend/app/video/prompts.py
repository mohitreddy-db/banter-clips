"""Prompt construction.

Three rules here were learned from real renders, not from documentation:

1. Name the person. Removing the name to suppress text also removes the
   likeness — a named star renders accurately without any reference image.
2. State the no-lettering rule positively on the wardrobe ("a plain kit with
   no lettering"), not only as a trailing negative. Trailing negatives alone
   produced garbled shirt text and leaked brand boards in every early render.
3. Say "photograph", explicitly and every time. A scene once rendered as a
   cartoon illustration because the only mention of photorealism lived in the
   style bible, and a model-authored style line had replaced it.

None of the three is sufficient alone; all go in every prompt.
"""

from __future__ import annotations

import re

from .types import Scene, VideoPlan

STYLE_BIBLE = (
    "Cinematic photoreal sports comedy, modern 35mm film look, shallow depth of field, "
    "bright broadcast lighting, vertical 9:16 composition, obvious visual comedy, "
    "highly detailed faces and fabric texture"
)

# The medium anchor. Separate from the style bible on purpose: the bible is
# taste (grade, lens, mood) and may be flavoured per job, but this states what
# the output physically IS and is never overridable. One scene came back as an
# isometric cartoon when this clause did not exist.
PHOTOREAL = (
    "This is a REAL PHOTOGRAPH captured on a real camera with real human beings: "
    "photorealistic, live action, true-to-life skin texture, real fabric, real "
    "lighting and real depth of field. "
    "It is NOT an illustration, NOT a cartoon, NOT anime, NOT a 3D render, "
    "NOT CGI, NOT a painting, NOT a digital drawing, NOT a comic, "
    "NOT stylised or flat-shaded artwork"
)

# Appended to every image and motion prompt.
NEGATIVES = (
    "Absolutely no on-screen captions, subtitles, watermarks, brand logos, "
    "advertising boards, signage, scoreboards, crests, wordmarks, or readable text "
    "anywhere in the frame. No team logos. No collages or multi-panel layouts. "
    "Nothing in the scene may carry writing of any kind"
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

# Words that change the MEDIUM rather than the look. A planner is asked for
# grade and mood only, but asking is not enforcing — these are stripped from
# any model-authored style line before it reaches an image model.
_MEDIUM_WORDS = re.compile(
    r"\b(?:cartoon\w*|anime|animat\w+|illustrat\w+|render\w*|cgi|3-?d|"
    r"paint\w+|drawing|drawn|comic|stylis\w+|styliz\w+|sketch\w*|vector|"
    r"flat[- ]shaded|cel[- ]shaded|pixar|disney|storybook|isometric)\b",
    re.IGNORECASE,
)

# Props that force an image model to render lettering. Detected so the prompt
# can explicitly blank them; the planner is also told not to use them at all.
TEXT_PROPS = re.compile(
    # Capturing so findall yields the singular stem ("poll", not "polls").
    r"\b(newspaper|magazine|tabloid|phone|smartphone|tablet|ipad|laptop|"
    r"screen|monitor|television|tv|scoreboard|sign|signage|banner|poster|"
    r"billboard|whiteboard|chalkboard|clipboard|book|letter|document|"
    r"paperwork|chart|graph|poll|ballot|headline|placard|plaque|certificate|"
    r"contract|ticket|label|jersey number|nameplate)s?\b",
    re.IGNORECASE,
)


def safe_style(style: str) -> str:
    """Strip medium-changing words from a model-authored style line.

    "harsh spotlights, animated cel-shaded grade" becomes "harsh spotlights,
    grade". Keeps the model's taste, removes its ability to change what the
    output physically is.
    """
    cleaned = _MEDIUM_WORDS.sub("", str(style or ""))
    cleaned = re.sub(r"\s*,\s*,+", ",", cleaned)          # collapse emptied items
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" ,.;-")


def text_props_in(*fields: str) -> list[str]:
    """Text-bearing props mentioned in a scene, lowercased and deduplicated."""
    found: list[str] = []
    for field in fields:
        for match in TEXT_PROPS.findall(str(field or "")):
            word = match.lower()
            if word not in found:
                found.append(word)
    return found

TONE_DIRECTION = {
    "Funny": "warm absurdist physical comedy; nobody is humiliated",
    "Savage": "sharp, cocky mockery aimed at the situation rather than at a person's dignity",
    "Hype": "triumphant, loud, celebratory energy",
    "Bold": "confident, declarative, unbothered swagger",
}


def style_for(plan: VideoPlan) -> str:
    """The house look, always. Any per-job style is additive flavour.

    This used to read `plan.style or STYLE_BIBLE`, which let a model-authored
    style line REPLACE the bible — and with it the word "photoreal", the only
    thing keeping the render photographic. A scene came back as a cartoon
    illustration. The bible now always leads; job style may only add grade,
    lighting and mood after it.
    """
    tone = TONE_DIRECTION.get(plan.tone, TONE_DIRECTION["Bold"])
    extra = str(plan.style or "").strip().rstrip(".")
    flavour = f" {extra}." if extra and extra != STYLE_BIBLE else ""
    return f"{STYLE_BIBLE}.{flavour} Tone: {tone}"


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
    """The keyframe. One frame, one camera position — no motion, no dialogue.

    PHOTOREAL leads and closes the prompt. Models weight the opening and the
    ending most heavily, and the medium is the one property we can never
    afford to lose: a stylised frame poisons the clip animated from it.
    """
    # A prop that normally carries writing gets an explicit blanking order.
    # The planner is told to avoid these entirely; this catches the ones that
    # slip through, which is what rejected two keyframes in a row once.
    props = text_props_in(scene.action, scene.venue)
    blanking = (
        f"Any {', '.join(props)} visible must be completely blank: "
        f"plain empty surfaces with absolutely no writing, print or symbols. "
        if props else ""
    )
    return (
        f"{PHOTOREAL}. "
        f"{style_for(plan)}. "
        f"{SINGLE_FRAME}. "
        f"Setting: {scene.venue}. "
        f"Subjects: {cast_clause(plan, scene)}. "
        f"Action: {scene.action}. "
        f"Framing: {first_shot(scene.camera)}. "
        f"{blanking}"
        f"Keep the lower quarter of the frame visually calm. "
        f"{NEGATIVES}. "
        f"Remember: a real photograph of real people, never an illustration."
    )


# What to add to a retry, keyed by the phrase the review gate reports. Retrying
# an identical prompt mostly reproduces the identical defect, so each rejection
# reason buys a specific, stronger correction on the next attempt.
_CORRECTIONS = (
    ("not photoreal",
     "CRITICAL CORRECTION: the previous attempt came back as artwork. Produce a "
     "REAL PHOTOGRAPH shot on a real camera — real skin with pores and blemishes, "
     "real woven fabric, real lens depth of field, documentary realism. "
     "Absolutely no illustration, cartoon, render or painted look."),
    ("text visible",
     "CRITICAL CORRECTION: the previous attempt contained visible lettering. "
     "Every surface must be completely blank — no words, letters, numbers, "
     "symbols or writing anywhere, on clothing, walls, props or background."),
    ("logo",
     "CRITICAL CORRECTION: the previous attempt showed a brand or team logo. "
     "All clothing and surfaces must be plain unbranded solid colour."),
    ("collage",
     "CRITICAL CORRECTION: the previous attempt was split into panels. Produce "
     "ONE single uninterrupted photograph from ONE camera position."),
    ("severe defect",
     "CRITICAL CORRECTION: the previous attempt had anatomy errors. Render "
     "correct human anatomy: two arms, two legs, five fingers per hand, "
     "one clearly defined face per person."),
)


def escalate(prompt: str, reasons: list[str]) -> str:
    """Strengthen a prompt using why the last attempt was rejected."""
    blob = " ".join(reasons).lower()
    additions = [text for key, text in _CORRECTIONS if key in blob]
    if not additions:
        additions = ["Render this more carefully, exactly as described."]
    return f"{prompt} {' '.join(additions)}"


def build_motion_prompt(plan: VideoPlan, scene: Scene) -> str:
    """The animation. Describes only what moves, plus the spoken line.

    The generator performs the dialogue itself and lip-syncs it, so the line
    goes in the prompt rather than through a separate speech step.
    """
    speaker = plan.speaker_for(scene)
    parts = [
        f"{PHOTOREAL}. ",
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
- NEVER put a text-bearing prop in `action` or `venue`. Forbidden: newspapers,
  magazines, phones, tablets, laptops, screens, monitors, scoreboards, signs,
  banners, whiteboards, books, letters, documents, charts, polls, trophies with
  plaques, or anything a camera would show writing on. The image model renders
  lettering as garbled nonsense and the frame is rejected. Use physical,
  wordless props instead: balls, boots, kit bags, medals, confetti, trophies
  without plaques, furniture, food, weather.
- Every scene is LIVE ACTION photographed with a real camera. Never describe a
  cartoon, animation, illustration, diagram, isometric or bird's-eye "game
  board" view, or any composition that reads as artwork rather than a photo.
- Never invent a factual result, score, or quote presented as real news.
- `camera` describes ONE camera position only — a single framing such as
  "low-angle medium shot" or "slow push-in on his face". Never a shot list:
  no "then", no "cut to", no "wide shot followed by a close-up". A scene is
  one continuous take.
- `style` adds ONLY grade, lighting and mood on top of the house look —
  a few words such as "warm golden-hour grade, soft haze". It is never a
  replacement for the house style, never camera movement or editing, and it
  must never contradict live-action photography (no "animated", "cartoon",
  "illustrated", "rendered", "stylised").

Return ONLY JSON:
{{"title": "...",
  "style": "a few words of grade and mood only",
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
