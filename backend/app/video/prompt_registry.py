"""Registry of every prompt the pipeline sends to a model.

One entry per prompt: what it is for, which stage sends it, which model runs
it, and where the text lives. The texts themselves stay in `prompts.py`,
`review.py` and `research.py` — this module only catalogues them, so the
registry can never drift into being a second copy of a prompt.

Browse it:
    python -m app.video.prompt_registry            # list everything
    python -m app.video.prompt_registry planner    # print one full text

Human-readable companion: `PROMPTS.md` in this package.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from . import (captions, catalog_verify, enhancer, prompts, research, review,
               shotwriter, takes)


@dataclass(frozen=True)
class PromptSpec:
    key: str            # stable identifier
    kind: str           # "system" | "template" | "fragment"
    stage: str          # pipeline stage that sends it
    model: str          # settings key (or literal) of the model that runs it
    purpose: str        # one sentence: what this prompt is for
    text: str           # the actual prompt text or template


REGISTRY: tuple[PromptSpec, ...] = (
    PromptSpec(
        key="enhancer",
        kind="system",
        stage="enhance (before planning)",
        model="OPENAI_PLAN_MODEL",
        purpose=(
            "Sharpens a rough take into something specific, visual and "
            "speakable while keeping the stance, and reports who/what it is "
            "about plus any genuine ambiguity. Its output drives which "
            "questions the user is asked before any money is spent."
        ),
        text=enhancer.ENHANCER_SYSTEM,
    ),
    PromptSpec(
        key="take_enhancer",
        kind="system",
        stage="input page (on demand, repeatable)",
        model="OPENAI_PLAN_MODEL",
        purpose=(
            "Rewrites a fan's take into two sharper versions in DIFFERENT "
            "angles, for the Enhance button. Optimises for what actually "
            "spreads on Reels — a front-loaded hook, a visual situation, and "
            "enough disagreement to pull replies. Never reverses the stance; "
            "the original is always kept as a choice."
        ),
        text=takes.TAKE_ENHANCER_SYSTEM,
    ),
    PromptSpec(
        key="captions",
        kind="system",
        stage="publishing (on demand)",
        model="OPENAI_PLAN_MODEL",
        purpose=(
            "Three Instagram caption options in different registers — punchy, "
            "conversational, hype — with specific hashtags. Offered as a "
            "picker at publish time: a list gets chosen from, whereas a single "
            "suggestion gets ignored and a blank box stalls people."
        ),
        text=captions.CAPTION_SYSTEM,
    ),
    PromptSpec(
        key="planner",
        kind="system",
        stage="planning_story",
        model="OPENAI_PLAN_MODEL",
        purpose=(
            "Turns one sports take into a scene-by-scene JSON plan. Encodes the "
            "load-bearing rules: keep the user's stance, one speaker per scene "
            "with consecutive scenes differing (voice drift), one camera "
            "position per scene (collage defence), team palette without logos, "
            "no invented facts."
        ),
        text=prompts.PLANNER_SYSTEM,
    ),
    PromptSpec(
        key="shot_writer",
        kind="system",
        stage="planning_story (one call per job)",
        model="OPENAI_PLAN_MODEL",
        purpose=(
            "Writes the video prompt itself, as cinematography prose rather "
            "than fields joined by labels. Sees every shot at once so wardrobe "
            "and location phrasing stay identical across cuts. Writes the BODY "
            "only — the photoreal anchor, negatives, dialogue and no-subtitles "
            "rule are appended deterministically afterwards, because the one "
            "time a model was trusted with a guardrail it deleted it."
        ),
        text=shotwriter.SHOT_WRITER_SYSTEM,
    ),
    PromptSpec(
        key="review",
        kind="system",
        stage="generating_scenes",
        model="OPENAI_REVIEW_MODEL",
        purpose=(
            "Vision rubric that gates every keyframe before animation money is "
            "spent. Hard fails: visible text, real logos, collage, severe "
            "anatomy. Soft warns: hands, minor defects, subject doubt."
        ),
        text=review.SYSTEM,
    ),
    PromptSpec(
        key="image",
        kind="template",
        stage="generating_scenes",
        model="IMAGE_MODEL",
        purpose=(
            "The keyframe still. Camera-first labelled blocks, per Google's "
            "published Veo formula. Names the subject (holds the likeness), "
            "states the no-lettering wardrobe (kills garbled text), freezes "
            "the camera (kills collages). Built by build_image_prompt."
        ),
        text=(
            "{PHOTOREAL}. Camera: {shot_size, angle, LOCKED-OFF, lens}. "
            "Subject: {cast_clause}. Action, frozen mid-moment: {action}. "
            "Expression: {expression}. Blocking: {blocking}. "
            "Setting: {venue}. Lighting: {lighting}. Style: {style_for(plan)}. "
            "{SINGLE_FRAME}. {blanking of any text-props}. {FULL_FIGURE}. "
            "{NEGATIVES}."
        ),
    ),
    PromptSpec(
        key="motion",
        kind="template",
        stage="animating_scenes",
        model="VIDEO_MODEL",
        purpose=(
            "The animation pass on an approved keyframe. Camera / subject / "
            "action / context / style ordering as Veo and the Sora cookbook "
            "specify, with quantified beats for pacing, the speaker "
            "identified by appearance so the right face is lip-synced, and "
            "diegetic-only audio. Built by build_motion_prompt."
        ),
        text=(
            "Camera: {shot_size, angle, move, lens}. Subject: {cast_clause}. "
            "Action: {action}. Blocking: {blocking}. Timing: {beats}. "
            "Expression: {expression}. Setting: {venue}. Lighting: {lighting}. "
            'Dialogue: {name}, {short_look}, says, "{line}" — {delivery}. '
            "Ambient: {sfx}, under the dialogue. No music. "
            "Style: {style_for(plan)}. {PHOTOREAL}. Ends on: {transition}. "
            "{NEGATIVES}. No subtitles, no burned-in dialogue text."
        ),
    ),
    PromptSpec(
        key="reference_still",
        kind="template",
        stage="catalog_build (offline)",
        model="IMAGE_MODEL",
        purpose=(
            "Catalog reference stills: neutral studio identity shots (face "
            "close-up + full body) per character, generated with the SAME "
            "image model as scene keyframes so references and keyframes share "
            "a visual dialect."
        ),
        text=prompts.REFERENCE_STILL_PROMPT,
    ),
    PromptSpec(
        key="research",
        kind="template",
        stage="designing_characters (optional)",
        model="OPENAI_RESEARCH_MODEL",
        purpose=(
            "Web-search lookup for a cast member missing from the catalog: "
            "fetches appearance, current team and colours so an unknown name "
            "renders as a real look instead of a generic stand-in. Only runs "
            "with WEB_RESEARCH=openai."
        ),
        text=research.RESEARCH_PROMPT,
    ),
    PromptSpec(
        key="catalog_verify",
        kind="template",
        stage="catalog maintenance (offline, manual)",
        model="Firecrawl search → OPENAI_RESEARCH_MODEL (fallback: OpenAI web_search)",
        purpose=(
            "Checks a catalog entry against the web: current club, squad "
            "number, kit. Needed because wardrobes now assert specific facts "
            "that get rendered as legible text, so a stale entry produces a "
            "confidently wrong video rather than a vague one. Reports drift "
            "only — never rewrites the catalog."
        ),
        text=catalog_verify.VERIFY_PROMPT,
    ),
    PromptSpec(
        key="style_bible",
        kind="fragment",
        stage="all image and motion prompts",
        model="IMAGE_MODEL / VIDEO_MODEL",
        purpose="The house look: photoreal 35mm sports comedy, 9:16, detailed faces.",
        text=prompts.STYLE_BIBLE,
    ),
    PromptSpec(
        key="negatives",
        kind="fragment",
        stage="all image and motion prompts",
        model="IMAGE_MODEL / VIDEO_MODEL",
        purpose=(
            "Trailing ban on text, logos, crests and collages. Unreliable on "
            "its own (measured) — the review gate is the real defence — but it "
            "measurably lowers the defect rate."
        ),
        text=prompts.NEGATIVES,
    ),
    PromptSpec(
        key="single_frame",
        kind="fragment",
        stage="image prompts only",
        model="IMAGE_MODEL",
        purpose=(
            "Forces one continuous photograph. Added after a multi-shot camera "
            "direction produced a three-panel collage keyframe."
        ),
        text=prompts.SINGLE_FRAME,
    ),
    PromptSpec(
        key="photoreal",
        kind="fragment",
        stage="opens AND closes every image and motion prompt",
        model="IMAGE_MODEL / VIDEO_MODEL",
        purpose=(
            "The medium anchor — states that the output is a real photograph, "
            "never artwork. Non-overridable, deliberately separate from the "
            "style bible: a model-authored style line once replaced the bible "
            "and with it the only mention of photorealism, and a scene "
            "rendered as an isometric cartoon inside an otherwise real video."
        ),
        text=prompts.PHOTOREAL,
    ),
    PromptSpec(
        key="corrections",
        kind="fragment",
        stage="keyframe retries",
        model="IMAGE_MODEL",
        purpose=(
            "Per-defect corrective clauses appended on retry, chosen from what "
            "the review gate actually rejected. Resending an identical prompt "
            "mostly reproduces the identical defect."
        ),
        text="\n".join(f"[{key}] {text}" for key, text in prompts._CORRECTIONS),
    ),
    PromptSpec(
        key="tone_direction",
        kind="fragment",
        stage="style_for() in every prompt",
        model="IMAGE_MODEL / VIDEO_MODEL",
        purpose="Maps the product's four tones to concrete comedic direction.",
        text="\n".join(f"{k}: {v}" for k, v in prompts.TONE_DIRECTION.items()),
    ),
)


def get(key: str) -> PromptSpec | None:
    return next((p for p in REGISTRY if p.key == key), None)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        spec = get(argv[0])
        if spec is None:
            print(f"unknown prompt {argv[0]!r}. Known: {', '.join(p.key for p in REGISTRY)}")
            return 1
        print(f"key     {spec.key}\nkind    {spec.kind}\nstage   {spec.stage}"
              f"\nmodel   {spec.model}\n\n{spec.purpose}\n\n---\n{spec.text}")
        return 0
    for spec in REGISTRY:
        print(f"  {spec.key:<16} {spec.kind:<9} {spec.stage:<32} {spec.model}")
        print(f"  {'':<16} {spec.purpose}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
