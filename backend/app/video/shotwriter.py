"""The shot writer — a model that writes the video prompt itself.

Assembling prompts from fields with a template is reliable and reads like a
form. A video model responds better to prose written the way a cinematographer
talks, and a writer can add detail no field anticipated — a reflection, a
piece of business with the hands, how a movement decelerates.

So this replaces the descriptive BODY of the motion prompt, and only the body.
The guardrails are still bolted on deterministically afterwards by
`prompts.build_motion_prompt`: the photoreal anchor, the negatives, the
no-subtitles rule. That split is not fussiness — we shipped the other design
once. A model was allowed to author the style line, it replaced the style
bible, the word "photoreal" vanished from the prompt, and a scene rendered as
an isometric cartoon. A model may describe the shot; it may not delete the
rules.

One call per JOB, not per scene. Seeing every shot at once is what lets it
keep wardrobe, lighting and location phrasing identical across cuts, which is
what the guides mean by continuity — and it costs a fraction of a cent.

Never blocks: no key, a bad response, or a missing scene falls back to the
deterministic template, which is always correct if less lyrical.
"""

from __future__ import annotations

import json
import logging
import re

from .types import VideoPlan, _clean

log = logging.getLogger("banter.video.shotwriter")

# Prose long enough to direct a shot, short enough to stay inside the band
# every published guide recommends. Over-long prompts measurably restrict
# these models, so this is a ceiling and not a target.
MAX_BODY_WORDS = 170

SHOT_WRITER_SYSTEM = """\
You are a prompt engineer for AI video generation models — Veo, Sora, Kling,
Grok Imagine. You are given a comedy sketch already broken into shots, and you
write the prompt that will be sent to the video model for each one.

<how_these_models_read_a_prompt>
They weight the opening most heavily, so the camera and the subject go first.
They render what is stated and invent what is not — an unstated time of day,
wardrobe or mood will be chosen for you, so state the ones that matter.
They respond to physical, observable description and ignore abstractions:
"his jaw tightens and he looks away" works, "he feels embarrassed" does not.
They need motion described as motion — how something starts, accelerates and
settles — because a static description yields a static shot.
</how_these_models_read_a_prompt>

<what_each_prompt_must_cover>
Camera: shot size, angle, ONE movement, and lens with depth of field.
Subject: who is on screen, their build and face, and exactly what they wear.
Action: what physically happens, in order.
Timing: quantified beats inside the shot — "for the first second… by four
seconds… in the last beat". This is what produces pacing rather than a pose.
Expression and body language: precise and physical.
Environment: the location, what is in the background, what the crowd does.
Lighting: source, hardness, direction, colour.
Sound: one or two diegetic sounds that exist in that room. Never music.
</what_each_prompt_must_cover>

<hard_constraints>
- ONE camera setup and ONE continuous action per shot. Never a shot list,
  never "then", never "cut to". A second camera position inside one prompt
  makes the model render a split screen.
- Everything is live action photographed on a real camera.
- Keep every character's appearance and wardrobe phrased IDENTICALLY across
  shots. Rewording them makes the model render a different-looking person.
  Copy the wardrobe text you are given, word for word.
- Kit lettering is wanted: real club names, squad numbers and crests, stated
  as legible. Do not ask for blank or unbranded clothing.
- Do NOT write the dialogue line into your prompt — it is added separately.
- Do NOT mention captions, subtitles, watermarks, logos bans, aspect ratio,
  or the words "photorealistic" and "not a cartoon". Those are appended
  afterwards and repeating them wastes words the model could spend on the
  shot.
- Under {max_words} words per shot. Every word must earn its place: these
  models are documented to follow long prompts LESS reliably, not more.
</hard_constraints>

Return ONLY JSON, one entry per shot, in order:
{{"shots": [{{"index": 0, "prompt": "..."}}, ...]}}"""


def _scene_brief(plan: VideoPlan, scene) -> dict:
    speaker = plan.speaker_for(scene)
    return {
        "index": scene.index,
        "beat": scene.beat,
        "seconds": scene.seconds,
        "who_is_on_screen": [
            {"name": m.name, "look": m.look, "wardrobe": m.wardrobe}
            for m in ([speaker] if speaker else []) + [
                m for m in plan.cast if m is not speaker
            ][:1]
        ],
        "action": scene.action,
        "beats": scene.beats,
        "shot_size": scene.shot_size,
        "camera_angle": scene.camera_angle,
        "camera_move": scene.camera_move,
        "lens": scene.lens,
        "expression": scene.expression,
        "blocking": scene.blocking,
        "venue": scene.venue,
        "lighting": scene.lighting,
        "sfx": scene.sfx,
        "transition": scene.transition,
        "speaker_is_saying": scene.trimmed_line(),  # context only; not to be written in
    }


def write(plan: VideoPlan, client=None) -> dict[int, str]:
    """Scene index -> prompt body. Empty dict means use the template."""
    if client is None or not getattr(client, "available", False) or not plan.scenes:
        return {}

    payload = {
        "title": plan.title,
        "style": plan.style,
        "tone": plan.tone,
        "sport": plan.sport,
        "shots": [_scene_brief(plan, s) for s in plan.scenes],
    }
    system = SHOT_WRITER_SYSTEM.format(max_words=MAX_BODY_WORDS)
    try:
        raw = client.complete_json(
            system,
            "Write the video prompt for each shot.\n\n" + json.dumps(payload, indent=1),
            max_tokens=6000,
        )
        shots = _parse(raw)
    except Exception:  # noqa: BLE001 — the template is always available
        log.exception("shot writer failed; using the assembled template")
        return {}

    out: dict[int, str] = {}
    valid = {s.index for s in plan.scenes}
    for shot in shots:
        try:
            index = int(shot.get("index"))
        except (TypeError, ValueError):
            continue
        body = _clean(shot.get("prompt"))
        if index in valid and body:
            out[index] = _cap(body)
    if len(out) != len(plan.scenes):
        log.warning("shot writer returned %d of %d shots", len(out), len(plan.scenes))
    return out


def _cap(body: str) -> str:
    """Trim to the word ceiling at a sentence boundary where possible."""
    words = body.split()
    if len(words) <= MAX_BODY_WORDS:
        return body
    clipped = " ".join(words[:MAX_BODY_WORDS])
    cut = clipped.rfind(". ")
    return (clipped[: cut + 1] if cut > len(clipped) * 0.6 else clipped).strip()


def _parse(text: str | None) -> list[dict]:
    if not text:
        return []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", str(text), re.S)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    shots = data.get("shots") if isinstance(data, dict) else data
    return [s for s in shots if isinstance(s, dict)] if isinstance(shots, list) else []
