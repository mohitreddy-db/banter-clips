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
# Compressed deliberately. Every guide measured (OpenAI's Sora cookbook,
# Runway's Gen-4 notes) says over-long prompts restrict the model, so the
# boilerplate has to earn its words — every one it takes is a word of
# scene-specific direction it displaces. The load-bearing signal here is
# "real photograph" plus a short, explicit list of the media it is not.
PHOTOREAL = (
    "REAL PHOTOGRAPH on a real camera: live action, true skin texture, real "
    "fabric, real optical depth of field. Not animation, illustration, cartoon, "
    "anime, 3D render or painted art"
)

# Appended to every image and motion prompt.
NEGATIVES = (
    "No readable text anywhere: no captions, subtitles, watermarks, logos, "
    "crests, signage, scoreboards or advertising boards. No split screen, "
    "panels or collage"
)

# Framing. This replaced "keep the lower quarter of the frame visually calm",
# which was written to give burned-in captions a clean background but had an
# expensive side effect: the model honoured it by ENDING THE SUBJECT above the
# lower quarter. Measured — bodies terminated at ~78% of frame height, legs cut
# at mid-thigh, dead floor below. Constrain the clutter, not the subject.
FULL_FIGURE = (
    "Whole bodies in frame, heads and feet included, nobody cropped at the "
    "knees, a little headroom above; plain uncluttered ground along the "
    "bottom edge."
)

# Stills only. A camera direction like "wide shot, then a close-up" describes a
# sequence, and an image model renders a sequence as stacked panels — which is
# exactly how a keyframe came back as a three-panel collage. Say "one frame".
SINGLE_FRAME = (
    "ONE continuous photograph from ONE camera position — a single frozen "
    "instant, never two moments or two angles in the same image"
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


def cast_clause(plan: VideoPlan, scene: Scene, limit: int = 2) -> str:
    """Describe whoever should be visible, name first, wardrobe rule attached.

    Capped at two people. Three full descriptions ran to 127 words — more than
    the entire rest of the direction — and every one of those words displaces
    scene-specific detail the model would otherwise act on. Two is also what
    almost every scene actually contains.
    """
    speaker = plan.speaker_for(scene)
    members = [speaker] if speaker else []
    for member in plan.cast:
        if member not in members and len(members) < limit:
            members.append(member)
    if not members:
        return "a professional athlete in plain team-coloured kit with no lettering"
    return "; ".join(f"{m.name}, {m.look}, wearing {m.wardrobe}" for m in members if m)


def short_look(member) -> str:
    """A few words that pick this person out of a crowd.

    Used to attribute dialogue. The guides recommend identifying the speaker
    by appearance so the model lip-syncs the right face, but repeating the
    full description costs forty words for something already stated in the
    Subject block — the distinguishing clause alone does the same job.
    """
    if member is None:
        return ""
    words = str(member.look or "").split()
    return " ".join(words[:8]).rstrip(",;")


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
    parts = [
        f"{PHOTOREAL}.",
        # A still is one frozen instant, so the camera never moves here.
        f"Camera: {_camera_block(scene, single=True)}.",
        f"Subject: {cast_clause(plan, scene)}.",
        f"Action, frozen mid-moment: {scene.action}.",
    ]
    if scene.expression:
        parts.append(f"Expression: {scene.expression}.")
    if scene.blocking:
        parts.append(f"Blocking: {scene.blocking}.")
    parts.append(f"Setting: {scene.venue}.")
    if scene.lighting:
        parts.append(f"Lighting: {scene.lighting}.")
    parts.append(f"Style: {style_for(plan)}.")
    parts.append(SINGLE_FRAME + ".")
    if blanking:
        parts.append(blanking.strip())
    parts.append(FULL_FIGURE)
    parts.append(f"{NEGATIVES}.")
    parts.append("Remember: a real photograph of real people, never an illustration.")
    return " ".join(parts)


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


def _camera_block(scene: Scene, single: bool = False) -> str:
    """The four camera axes, labelled.

    Veo, Sora and Kling all document camera as separate axes — shot size,
    angle, movement, lens — and all three put camera FIRST. One free-text
    field made the model guess which axis a phrase meant, and invited shot
    lists, which render as split screens.
    """
    move = "locked-off static frame" if single else first_shot(scene.camera_move)
    parts = [
        first_shot(scene.shot_size) or "medium wide shot",
        scene.camera_angle or "eye level",
        move,
        scene.lens or "35mm, shallow depth of field",
    ]
    return ", ".join(p for p in parts if p)


def build_motion_prompt(plan: VideoPlan, scene: Scene) -> str:
    """The animation. Describes only what moves, plus the spoken line.

    The generator performs the dialogue itself and lip-syncs it, so the line
    goes in the prompt rather than through a separate speech step.
    """
    speaker = plan.speaker_for(scene)
    line = scene.trimmed_line()

    parts = [
        # Camera first, then subject, action, context, style — the ordering
        # Google publishes for Veo and OpenAI uses in the Sora cookbook.
        f"Camera: {_camera_block(scene)}.",
        f"Subject: {cast_clause(plan, scene)}.",
        f"Action: {scene.action}.",
    ]
    if scene.blocking:
        parts.append(f"Blocking: {scene.blocking}.")
    if scene.beats:
        # Quantified beats are what turn a pose into a performance; Sora's
        # guide is explicit that "walks four steps then pauses" outperforms
        # "walks across the room".
        parts.append(f"Timing: {scene.beats}.")
    if scene.expression:
        parts.append(f"Expression: {scene.expression}.")
    parts.append(f"Setting: {scene.venue}.")
    if scene.lighting:
        parts.append(f"Lighting: {scene.lighting}.")

    if line and speaker:
        # Attribute by name AND appearance: with several people in frame the
        # model otherwise guesses who is speaking and lip-syncs the wrong one.
        parts.append(
            f'Dialogue: {speaker.name}, {short_look(speaker)}, says, "{line}" '
            f"— {scene.delivery or speaker.voice}."
        )
    elif line:
        parts.append(f'Dialogue: one voice says, "{line}".')

    ambience = scene.sfx or "crowd murmur and shuffling feet"
    parts.append(f"Ambient: {ambience}, under the dialogue. No music.")
    parts.append(f"Style: {style_for(plan)}.")
    parts.append(f"{PHOTOREAL}.")
    if scene.transition:
        parts.append(f"Ends on: {scene.transition}.")
    # Veo is documented to burn in its own subtitles when given dialogue; we
    # burn our own captions with ffmpeg, so a second set would collide.
    parts.append(f"{NEGATIVES}. No subtitles, no burned-in dialogue text.")
    return " ".join(parts)


PLANNER_SYSTEM = """\
You are an Instagram Sports Banter Reels specialist. You turn one fan's
opinion into a shot-by-shot plan for a short vertical comedy video that gets
watched to the end, screenshotted, and argued about in the replies.

<what_makes_these_work>
Reach on Reels comes from retention and shares, and both are decided in the
first second. So: the funniest visual must be ON SCREEN immediately — no
build-up, no establishing shot, no title card. Every scene after it must
RAISE the premise rather than restate it, because a flat middle is where
people scroll. The last line is the one that gets quoted, so it lands the
joke rather than explaining it.

Comedy comes from a specific absurd SITUATION the camera can see — a person
doing something ridiculous with total commitment — never from wordplay,
narration or captions. If the joke needs explaining, it is the wrong joke.
Rivalry and mock-outrage travel further than praise: the reply guy is the
distribution channel.
</what_makes_these_work>

<hard_rules>
- Keep the user's stance. Sharpen and exaggerate it; never reverse or soften
  it. If they say a team is bad, the video says it harder.
- Exactly {scene_count} scenes: hook, then escalation, then payoff.
- Each scene has AT MOST ONE speaker, and consecutive scenes MUST use
  different speakers. This is a technical constraint, not a style note: the
  generator gives a character a different voice in every clip, so alternating
  speakers is what stops one character audibly changing voice mid-video.
- A line must be speakable inside its scene: at most {max_words} words.
- Cast only from the provided roster, using their exact `id` values.
- When the take targets a team, cast that team's players and use their colour
  palette and venues.
- Describe ONE continuous take per scene: one camera setup, one action. Never
  a shot list, never "then", never "cut to" — a second camera position inside
  one scene makes the image model render a split screen.
- Everything is LIVE ACTION photographed on a real camera. Never describe
  animation, illustration, diagrams, isometric or board-game views.
- NO text-bearing props anywhere: no newspapers, phones, tablets, screens,
  scoreboards, signs, banners, whiteboards, documents or plaques. Image
  models render lettering as garbled nonsense and the frame gets rejected.
  Use wordless props: balls, boots, kit bags, confetti, food, furniture.
- Never present an invented score, result, injury, transfer or quote as real.
- Mock performance, decisions and situations. Never mock a person's
  appearance, family, race or intelligence.
</hard_rules>

<how_to_fill_each_field>
Write for a video model that has no memory between shots, so each scene must
stand alone while matching the others.

- `action`: what physically happens, in the order it happens. Concrete verbs
  and specific objects. One sentence.
- `beats`: the timing inside the clip, quantified. e.g. "first second he
  stares; by three seconds the pile collapses; he never reacts". This is what
  gives the model pacing instead of a static pose.
- `shot_size`: wide shot / full shot / medium shot / medium close-up /
  close-up. Prefer wide and full — this is a tall 9:16 frame and physical
  comedy needs whole bodies.
- `camera_angle`: eye level / low angle / high angle / over-the-shoulder.
- `camera_move`: ONE move — slow push-in, slow pull-back, tracking left,
  handheld follow, locked-off static.
- `lens`: focal length and depth of field, e.g. "35mm, shallow depth of
  field".
- `expression`: the speaker's face and body language, precisely. "Completely
  unbothered, eyebrows raised a millimetre" beats "looks smug".
- `blocking`: where people are in the frame and how they move relative to
  each other.
- `lighting`: source, quality and direction, e.g. "hard overhead arena
  floodlights, deep shadows under the eyes".
- `sfx`: one or two DIEGETIC sounds that exist in the room. Never music.
- `transition`: one clause on how this shot hands over to the next, so the
  cut feels intentional.
- `venue`: reuse the SAME wording for a location across scenes that share it.
  Identical phrasing is what keeps the world continuous.

Repeat character and wardrobe descriptions verbatim between scenes. Rewording
them makes the model render a different-looking person.
</how_to_fill_each_field>

Return ONLY JSON:
{{"title": "...",
  "style": "a few words of grade and mood only",
  "focus": "player|team|matchup|generic",
  "teams": ["team ids the video leans on, may be empty"],
  "cast": [{{"id": "...", "name": "...", "look": "...", "wardrobe": "...", "voice": "..."}}],
  "scenes": [{{"beat": "hook|escalation|payoff", "venue": "...", "action": "...",
              "beats": "...", "shot_size": "...", "camera_angle": "...",
              "camera_move": "...", "lens": "...", "expression": "...",
              "blocking": "...", "lighting": "...", "sfx": "...",
              "transition": "...", "speaker_id": "...", "line": "...",
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
