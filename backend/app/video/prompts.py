"""Prompt construction.

Three rules here were learned from real renders, not from documentation:

1. Name the person. Removing the name to suppress the likeness also removes
   the likeness — a named star renders accurately without a reference image.
2. Ask for the AUTHENTIC kit, by team, with the name and number spelled out.
   The opposite rule shipped first and was wrong: telling a model a jersey
   must carry no lettering does not remove the lettering, it degrades it into
   gibberish ("RUACIS" where "SPURS" belonged). A controlled A/B rendered
   "SPURS 1" cleanly when simply asked for the real kit.
3. Say "photograph", explicitly and every time. A scene once rendered as a
   cartoon illustration because the only mention of photorealism lived in the
   style bible, and a model-authored style line had replaced it.

None of the three is sufficient alone; all go in every prompt.
"""

from __future__ import annotations

import re
import unicodedata

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
    "REAL PHOTOGRAPH on a real camera: true skin texture, real fabric, real "
    "optical depth of field. Never animation, illustration, cartoon, anime, "
    "3D render or painted art"
)

# Appended to every image and motion prompt.
#
# The "exactly once" rule is here rather than in its own clause so it reaches
# both prompts for a dozen words. Two clips reviewed on 2026-08-28 rendered a
# person twice: a bench shot with a second Mbappé bent over behind it, and a
# frame containing two Vinícius/Mourinho/Mbappé pairs side by side. Nothing in
# the prompt had ever said a person may not be duplicated.
NEGATIVES = (
    "No captions, subtitles or watermarks (added later); no split screen, "
    "panels or collage. Each person appears EXACTLY ONCE — never a twin, "
    "clone, mirrored or look-alike copy of anyone, foreground or background"
)

# Every clip reviewed on 2026-08-20 carried invented lettering somewhere the
# prompt was silent — sponsor "Hobiin" on a jersey, "ffe far" arena boards, a
# gibberish scoreboard. Models render named text cleanly and unnamed text as
# alien script, so unnamed surfaces must be explicitly plain.
CLEAN_TEXT = (
    "Readable lettering only where named: kit crests, names, numbers, props. "
    "Ad boards, scoreboards and signage stay plain or unreadable"
)

# Framing. This replaced "keep the lower quarter of the frame visually calm",
# which was written to give burned-in captions a clean background but had an
# expensive side effect: the model honoured it by ENDING THE SUBJECT above the
# lower quarter. Measured — bodies terminated at ~78% of frame height, legs cut
# at mid-thigh, dead floor below. Constrain the clutter, not the subject.
FULL_FIGURE = (
    "Whole bodies in frame, heads and feet included, never cropped at the "
    "knees; plain uncluttered ground at the bottom edge."
)

# Stills only. A camera direction like "wide shot, then a close-up" describes a
# sequence, and an image model renders a sequence as stacked panels — which is
# exactly how a keyframe came back as a three-panel collage. Say "one frame".
SINGLE_FRAME = (
    "ONE photograph from ONE camera position — one frozen instant, never "
    "two moments or two angles"
)

# Cross-shot drift: within one video, Arteta rendered in a plain shirt, a
# retro O2-era shirt, then beside a fan in an "ARTETA 9" jersey (observed
# 2026-08-21). Every shot's keyframe states the continuity contract.
WORLD_LOCK = (
    "Continuity: one filmed video — same location, light and wardrobe in "
    "every shot"
)

# Words that cannot end a description of a person: articles, intensifiers,
# prepositions and bare adjectives all leave the fragment describing nothing.
_DANGLING = re.compile(
    r"(?:a|an|the|very|extremely|quite|really|with|and|of|in|his|her|their|"
    r"tall|short|slim|thin|slight|fast|quick|compact|stocky|lean|big|small|"
    r"young|old|broad|heavy|light|strong|muscular|athletic|wiry|burly)",
    re.IGNORECASE,
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


def _plain(text: object) -> str:
    """Lowercase and accent-stripped, so "Mbappé" in an action matches a cast
    member written "Kylian Mbappe"."""
    stripped = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in stripped if not unicodedata.combining(c)).lower()


def visible_cast(plan: VideoPlan, scene: Scene, limit: int = 2) -> list:
    """Who is actually in this shot, most important first.

    One source of truth for both the prompt text and the reference stills the
    runner attaches — when those disagreed, a shot whose action was entirely
    about Mbappé was anchored to a photo of Mourinho, and the model resolved
    the contradiction by drawing extra people.

    A speaker with a line must be visible to be lip-synced, so they lead.
    In a silent shot "speaker" is a leftover field, so whoever the action
    actually names leads instead.
    """
    speaker = plan.speaker_for(scene)
    text = _plain(f"{scene.action or ''} {scene.blocking or ''}")
    named = [
        m for m in plan.cast
        if any(len(tok) >= 4 and tok in text for tok in _plain(m.name).split())
    ]
    head = ([speaker] if (speaker and scene.line) else []) + named
    ordered: list = []
    for member in head + list(plan.cast):
        if member is not None and member not in ordered:
            ordered.append(member)
    return ordered[:limit]


def _trim_clause(text: object, limit: int) -> str:
    """Shorten to roughly `limit` words, cutting at a clause boundary so the
    fragment never dangles mid-phrase."""
    text = str(text or "").strip().rstrip(".")
    if len(text.split()) <= limit:
        return text
    kept: list[str] = []
    for clause in re.split(r"(?<=[,;])\s*", text):
        if kept and len(" ".join(kept + [clause]).split()) > limit:
            break
        kept.append(clause)
    joined = " ".join(kept).strip().rstrip(" ,;.")
    return joined or " ".join(text.split()[:limit]).rstrip(" ,;.")


def cast_clause(plan: VideoPlan, scene: Scene, limit: int = 2) -> str:
    """Describe whoever should be visible, name first, wardrobe rule attached.

    Capped at two people, and each description capped in turn: a research-
    enriched look plus wardrobe ran to 102 words for two people — a third of
    the whole prompt spent on appearance the reference stills already carry
    far more precisely, displacing the scene-specific detail the model would
    otherwise act on.
    """
    members = [m for m in visible_cast(plan, scene, limit) if m]
    if not members:
        return "a professional athlete in an authentic team kit"
    # Teammates share a kit, and describing it twice cost 25 words to say the
    # same sentence again. The wardrobe itself is never trimmed — exact kit
    # detail is the thing that makes a frame read as real footage — so the
    # words come out of the duplication and the adjective pile instead.
    if (len(members) == 2 and members[0].wardrobe
            and _plain(members[0].wardrobe) == _plain(members[1].wardrobe)):
        first, second = members
        return (f"{first.name}, {_trim_clause(first.look, 16)}; "
                f"{second.name}, {_trim_clause(second.look, 16)}; "
                f"both wearing {first.wardrobe}")
    return "; ".join(
        f"{m.name}, {_trim_clause(m.look, 16)}, wearing {m.wardrobe}" for m in members
    )


def short_look(member) -> str:
    """A few words that pick this person out of a crowd.

    Used to attribute dialogue. The guides recommend identifying the speaker
    by appearance so the model lip-syncs the right face, but repeating the
    full description costs forty words for something already stated in the
    Subject block — the distinguishing clause alone does the same job.
    """
    if member is None:
        return ""
    look = str(member.look or "").strip()
    if not look:
        return ""
    # Pick the first clause that stands on its own. Accumulating clauses until
    # three words were reached still produced "Wembanyama, an extremely tall,
    # says" and "Mbappe, a fast, says" — three words of pure modifier that
    # describe nobody. A clause ending in a qualifier is never the answer, and
    # trailing qualifiers left by the length cap are dropped for the same
    # reason.
    for clause in (c.strip() for c in re.split(r"[,;]", look) if c.strip()):
        words = clause.split()[:12]
        while words and _DANGLING.fullmatch(words[-1].strip(".,;")):
            words.pop()
        if len(words) >= 3:
            return " ".join(words).rstrip(" ,;.")
    return _trim_clause(look, 12)


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
    parts.append(f"{WORLD_LOCK}.")
    parts.append(FULL_FIGURE)
    parts.append(f"{CLEAN_TEXT}.")
    parts.append(f"{NEGATIVES}.")
    parts.append("Remember: a real photograph, never an illustration.")
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
    ("garbled",
     "CRITICAL CORRECTION: lettering in the previous attempt was malformed. "
     "Render every word correctly spelled and cleanly typeset — real kit "
     "names, squad numbers and crests in a consistent, sharp typeface. If a "
     "word cannot be rendered cleanly, leave that surface plain instead."),
    ("collage",
     "CRITICAL CORRECTION: the previous attempt was split into panels. Produce "
     "ONE single uninterrupted photograph from ONE camera position."),
    ("severe defect",
     "CRITICAL CORRECTION: the previous attempt had anatomy errors. Render "
     "correct human anatomy: two arms, two legs, five fingers per hand, "
     "one clearly defined face per person."),
    ("appears twice",
     "CRITICAL CORRECTION: the previous attempt drew the same person more "
     "than once. Every named person must appear exactly ONE time in the "
     "frame — no twin, no clone, no mirrored copy, and no look-alike of them "
     "standing in the background."),
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

    if scene.shot_prompt:
        # A shot writer described the cinematography in prose. Use it as the
        # body; the guardrails below are still appended, because the one time
        # a model was trusted with them it dropped "photoreal" and a scene
        # came back a cartoon.
        parts = [scene.shot_prompt.rstrip(". ") + "."]
    else:
        parts = [
            # Camera first, then subject, action, context, style — the ordering
            # Google publishes for Veo and OpenAI uses in the Sora cookbook.
            f"Camera: {_camera_block(scene)}.",
            f"Subject: {cast_clause(plan, scene)}.",
            f"Action: {scene.action}.",
        ]
    if not scene.shot_prompt:
        if scene.blocking:
            parts.append(f"Blocking: {scene.blocking}.")
        if scene.beats:
            # Quantified beats turn a pose into a performance; Sora's guide is
            # explicit that "walks four steps then pauses" beats "walks across
            # the room".
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
        # Naming the speaker was not enough on its own: clips reviewed on
        # 2026-08-28 had TWO people lip-syncing one line in identical sync
        # (Bellingham and Mourinho on a bench; Vinícius and Mbappé while
        # Mourinho's line played).
        #
        # It forbids LIP-SYNC, not open mouths. Scripts legitimately direct a
        # reaction — one action read "both mouths agape" — and a blanket
        # "everyone keeps their mouth closed" would contradict the shot's own
        # description in the same prompt. Reacting is fine; mouthing the words
        # is not.
        speech_rule = (
            f"Only {speaker.name}'s lips move in sync with the line. Nobody "
            "else speaks, mouths or echoes it — other faces react in silence. "
            "One voice on the track."
        )
    elif line:
        parts.append(f'Dialogue: one voice says, "{line}".')
        speech_rule = "Exactly one speaker; no other lips move in sync with the line."
    else:
        # A silent cutaway said nothing about speech at all, which left the
        # model free to invent mouth movement over an empty soundtrack.
        speech_rule = "No dialogue in this shot: nobody speaks and no lips move."

    if scene.shot_prompt:
        parts.append("Audio is diegetic only, under the dialogue. No music.")
    else:
        ambience = scene.sfx or "crowd murmur and shuffling feet"
        parts.append(f"Ambient: {ambience}, under the dialogue. No music.")
        parts.append(f"Style: {style_for(plan)}.")
    # In-shot drift is a real failure mode: a defender's kit faded from blue
    # to white across one generated clip (observed 2026-08-20). Naming the
    # constancy explicitly is the documented mitigation.
    parts.append(
        "Every kit, colour and prop stays exactly as in the first frame — "
        "clothing never changes colour or design."
    )
    parts.append(f"{PHOTOREAL}.")
    if scene.transition and not scene.shot_prompt:
        parts.append(f"Ends on: {scene.transition}.")
    # Veo is documented to burn in its own subtitles when given dialogue; we
    # burn our own captions with ffmpeg, so a second set would collide.
    parts.append(f"{NEGATIVES}. No subtitles, no burned-in dialogue text. "
                 "Background signage and scoreboards stay unreadable.")
    # Last, because models weight the end of a prompt most heavily and this
    # rule has to win against a shot description that may itself put several
    # mouths in motion.
    parts.append(speech_rule)
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

<if_the_take_is_a_brief>
Some users type a full production brief instead of an opinion ("Create a
15-sec funny roast: X happens, then Y, end with Z…"). When the take contains
explicit instructions — named people, ordered beats, a specified ending,
requested on-screen text — those are REQUIREMENTS, not inspiration:
- Same plot, same order of events, same characters. You add cinematic
  detail (camera, lighting, timing, expressions, blocking); you never
  substitute a different story or different people.
- Every person the brief names MUST appear in the cast, as themselves.
- A requested ending or closing text becomes the payoff scene, verbatim.
- If the brief asks for something this pipeline cannot do (music tracks,
  real footage), simply omit it — never replace it with something else.
</if_the_take_is_a_brief>

<hard_rules>
- Keep the user's stance. Sharpen and exaggerate it; never reverse or soften
  it. If they say a team is bad, the video says it harder.
- Exactly {scene_count} SHOTS telling ONE story in ONE location, with the
  arc hook → escalation → payoff across them. This is a film set, not a
  slideshow: every shot happens in the same place, minutes apart at most.
- ONE WORLD: every shot's `venue` is the SAME text, word for word. Props
  that exist in one shot exist in all later shots, described with the same
  words ("three black gym bags on the pavement"). Light and weather never
  change. The video must feel like one continuous filmed moment.
- Shot lengths vary like a real edit, and the total must be {total_seconds}
  seconds: ONE anchor shot of 5-8 seconds carrying the main dialogue
  moment, the rest cutaways of 2.5-4 seconds (reactions, the physical gag,
  a detail). Set each shot's `seconds` yourself.
- Each shot has AT MOST ONE speaker, and consecutive shots MUST use
  different speakers (or a silent reaction shot between two lines from the
  same person). This is a technical constraint: the generator gives a
  character a different voice in every clip, so alternating speakers stops
  one character audibly changing voice mid-video.
- Cutaways may be SILENT (empty line) — a wordless reaction often lands
  harder than a line.
- A line must be speakable inside its shot: at most 2.2 words per second
  of that shot's length. Long speech belongs in the anchor shot.
- When real-world context is provided, USE it: real storylines beat
  invented ones, real people beat generic characters, the real kit and a
  real place beat any invention. Never contradict the context, and never
  use anything its AVOID list mentions.
- Casting: use roster members (by their exact `id`) when the story is about
  them — but the roster is NOT a limit. When the take names a real figure
  who is not on it, cast them anyway: invent a short id, and write their
  real appearance, their real club's kit, and a fitting voice. Never swap a
  named person for a lookalike or a roster member ("Ronaldinho" is not
  "Ronaldo"). When the story is about fans or a crowd, cast generic
  characters (a die-hard fan in the team's shirt and scarf, a steward) —
  never dress a superstar as a stand-in for a fan.
- Wardrobe follows the STORY, not the roster entry: a player acting in an
  Arsenal story wears the Arsenal kit described in the team context, not
  their own club's kit.
- Managers, coaches and staff wear STAFF clothing — a touchline jacket,
  club quarter-zip or suit — never a player's numbered shirt.
- Each person wears EXACTLY ONE outfit for the whole video, described with
  the same words in every shot — a kit that changes era or sponsor between
  shots breaks the video.
- When the take targets a team, cast that team's players and use their colour
  palette and venues.
- Describe ONE continuous take per scene: one camera setup, one action. Never
  a shot list, never "then", never "cut to" — a second camera position inside
  one scene makes the image model render a split screen.
- Everything is LIVE ACTION photographed on a real camera. Never describe
  animation, illustration, diagrams, isometric or board-game views.
- Props may carry writing — scoreboards, signs, banners, boards. When one
  does, state EXACTLY what it should say in short block capitals, because a
  model given specific short text renders it cleanly while a model left to
  invent text renders gibberish. A few words at most.
- Props are REAL-WORLD SCALE and physically plausible, held or placed the
  way a real person would. Never giant, shrunken, floating, or embedded-in-
  the-ground objects — an impossible prop reads as an AI mistake, not a
  joke. Stage a metaphor through human PERFORMANCE with normal props: a
  player casually holding a normal game controller sells "demo mode"; a
  knee-high controller planted in the turf kills the video's credibility.
- A prop that appears in more than one scene is described with the SAME
  words every time, like wardrobe — reworded props change model and colour.
- Never present an invented score, result, injury, transfer or quote as real.
- Mock performance, decisions and situations. Never mock a person's
  appearance, family, race or intelligence.
- The payoff is a PHYSICAL comedic moment performed by the cast in-scene —
  a reaction, a reveal, an escalation completed. Never a person holding a
  homemade sign, never an empty-jersey tableau, never a summary shot: the
  last scene is the one that gets shared, so it must be the strongest image,
  not a caption card.
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

- `speaker_id` is the person the shot is BUILT AROUND, and it must be someone
  the `action` actually shows. One shot spoke as the manager while its action
  was entirely about a forward, so the wrong face was anchored and the render
  drew both. In a silent shot (`line` empty) name whoever the action is about.
- Exactly one person speaks per shot. Never write an action where two people
  say the same thing, speak in unison, or echo each other.
- Never place the same person in a shot twice — no body double, no "and a
  second Mbappé", no mirrored version of someone already on screen.
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
              "delivery": "...", "seconds": <this shot's length>}}]}}"""


def planner_user_message(
    take: str, sport: str, tone: str, roster: list, venues: list,
    focus_note: str = "", storyline: str = "",
) -> str:
    names = "\n".join(f"  - id={m.id!r} name={m.name!r} ({m.look})" for m in roster)
    places = "\n".join(f"  - {v}" for v in venues)
    context = f"\n{focus_note}\n" if focus_note else ""
    world = f"\n{storyline}\n" if storyline else ""
    return (
        f"Sport: {sport}\n"
        f"Tone: {tone}\n"
        f"The opinion to dramatise: {take}\n"
        f"{world}"
        f"{context}\n"
        f"Pre-described roster (use these ids when casting these people; the "
        f"roster is not a limit — see the casting rule):\n{names}\n\n"
        f"Stock locations (prefer a REAL setting from the context above when "
        f"one exists):\n{places}\n"
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
    # Anatomy is spelled out because reference defects COMPOUND: a distorted
    # still anchors every future keyframe of this person. Kit exactness is
    # the point of the still: it carries team identity into every scene.
    "Accurate natural human proportions — correct head-to-body ratio, "
    "realistic limb lengths, an athletic adult physique photographed with a "
    "standard portrait lens, no wide-angle distortion. "
    "The kit is the person's REAL kit, reproduced faithfully: the exact true "
    "team colours and shade, the actual jersey design and trim, the real "
    "crest, with the name and number sharp, correctly spelled and clearly "
    "readable — never a generic or invented kit. "
    "Extremely high facial and body detail. "
    + SINGLE_FRAME + ". " + NEGATIVES + "."
)

# The reference set is four views, each with its own framing AND canvas.
# The canvas matters: a head-and-shoulders close-up forced onto a 9:16 canvas
# made the model fill the tall frame with a vertically squashed body
# (observed 2026-08-21) — portrait crops get 3:4, only the standing figure
# gets 9:16.
REFERENCE_VIEWS = {
    "face": {
        "framing": "Tight head-and-shoulders close-up, face perfectly sharp and "
                   "centred, filling the frame; skin texture, hairline and eyes "
                   "in maximum detail",
        "aspect": "3:4",
    },
    "full": {
        "framing": "Full-body shot from head to feet, whole figure visible and "
                   "centred, standing naturally with weight on both feet; every "
                   "item worn is visible and in focus — jersey, shorts, socks "
                   "and footwear all sharp",
        "aspect": "9:16",
    },
    "kit": {
        "framing": "Torso-only detail shot of the jersey filling the frame: "
                   "exact fabric colours and shade, the crest, every logo, the "
                   "name and number — all lettering perfectly sharp, correctly "
                   "spelled and legible",
        "aspect": "3:4",
    },
    "gear": {
        "framing": "Waist-down detail shot: shorts, socks and footwear filling "
                   "the frame, their exact colours, trim, logos and laces sharp "
                   "and in focus",
        "aspect": "3:4",
    },
}
