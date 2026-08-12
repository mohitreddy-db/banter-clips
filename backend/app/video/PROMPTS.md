# Prompt registry

Every prompt this pipeline sends to a model, what it is for, and which model
runs it. The machine-readable version is `prompt_registry.py`
(`python -m app.video.prompt_registry` lists everything;
`python -m app.video.prompt_registry planner` prints one full text).
Prompt texts live in `prompts.py`, `review.py` and `research.py` — this file
and the registry only describe them.

| Key | Kind | Sent during | Runs on | Purpose |
|---|---|---|---|---|
| `enhancer` | system | `enhance` (before planning) | `OPENAI_PLAN_MODEL` (gpt-4.1) | Sharpens a rough take into something specific, visual and speakable without changing the stance; reports subjects, teams and genuine ambiguity. Drives which questions the user is asked before any spend. |
| `planner` | system | `planning_story` | `OPENAI_PLAN_MODEL` (gpt-4.1) | Take → scene-by-scene JSON plan. Encodes the load-bearing rules: keep the stance; one speaker per scene, consecutive scenes differ (voice drift); one camera position per scene (collage defence); no text-bearing props; live action only; team palette without logos; no invented facts. |
| `review` | system | `generating_scenes` | `OPENAI_REVIEW_MODEL` (gpt-4o-mini, vision) | Gates every keyframe before animation money is spent. Hard fail: text, real logos, collage, severe anatomy. Soft warn: hands, minor defects, subject doubt. |
| `image` | template | `generating_scenes` | `IMAGE_MODEL` (grok-imagine-image-quality) | The keyframe still. Names the subject (holds the likeness), states the no-lettering wardrobe (kills garbled text), pins ONE camera position (kills collages). Built by `prompts.build_image_prompt`. |
| `motion` | template | `animating_scenes` | `VIDEO_MODEL` (grok-imagine-video-1.5) | Animates an approved keyframe. Motion + the spoken line only — the video model performs and lip-syncs dialogue natively. Built by `prompts.build_motion_prompt`. |
| `reference_still` | template | `catalog_build` (offline) | `IMAGE_MODEL` — **same model as keyframes, on purpose** | Neutral-studio identity stills (face close-up + full body) for the character catalog. |
| `research` | template | `designing_characters` (only if `WEB_RESEARCH=openai`) | `OPENAI_RESEARCH_MODEL` + web_search tool | Looks up an off-catalog name so it renders as a real appearance instead of a generic stand-in. Appearance only — never scores or quotes. |
| `style_bible` | fragment | every image/motion prompt | image + video models | House look: photoreal 35mm sports comedy, 9:16, detailed faces and fabric. |
| `negatives` | fragment | every image/motion prompt | image + video models | Trailing ban on text/logos/crests/collages. Measured as unreliable alone — the review gate is the real defence — but it lowers the defect rate. |
| `single_frame` | fragment | image prompts only | image model | Forces one continuous photograph. Added after a multi-shot camera direction produced a three-panel collage keyframe. |
| `photoreal` | fragment | **opens and closes** every image/motion prompt | image + video models | The medium anchor: this is a real photograph, never artwork. Non-overridable. |
| `corrections` | fragment | keyframe retries | image model | Per-defect corrective clauses chosen from what the gate rejected. |
| `tone_direction` | fragment | `style_for()` in every prompt | image + video models | Maps Funny / Savage / Hype / Bold to concrete comedic direction. |

## Rules for editing prompts

1. Edit the text in its home module (`prompts.py` / `review.py` /
   `research.py` / `enhancer.py`), never in the registry — the registry
   references, it does not copy.
2. Four clauses are load-bearing and guarded by tests. Each maps to a defect
   we actually shipped:

   | Clause | Removing it caused |
   |---|---|
   | Name the person **and** forbid lettering | generic stand-in / garbled kit text |
   | One camera position per scene | three-panel collage keyframe |
   | `PHOTOREAL`, never replaceable by job style | a cartoon scene inside a photoreal video |
   | No text-bearing props | two consecutive keyframe rejections, $0.10 burnt |

3. **Job style is additive, never a replacement.** `style_for()` always leads
   with `STYLE_BIBLE`; a model-authored style may only add grade and mood, and
   `safe_style()` strips any medium word (cartoon, render, illustrated…) that
   sneaks in. The original bug was `plan.style or STYLE_BIBLE`.
4. Product copy (captions, watermark, AI/parody disclosure) is never asked of
   a model — ffmpeg burns it deterministically (`media.brand`).
