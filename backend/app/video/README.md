# app/video — the generation workflow

Turns a take into a finished 9:16 MP4. The design this implements is
[`VIDEO-GENERATION-PLAN.md`](../../VIDEO-GENERATION-PLAN.md); this file is how
the code is laid out and how to run it. Every prompt sent to a model is
catalogued in [`PROMPTS.md`](PROMPTS.md) / `prompt_registry.py`.

## The one rule

**A job always produces a video.** Missing take, unknown sport, no API keys, a
model returning garbage, a scene that will not render — each degrades to
something weaker rather than failing the job. Only two things are fatal: no
`ffmpeg`, or not a single usable scene.

Degradation ladder, applied per scene:

```
real keyframe   ->  placeholder still
real animation  ->  Ken Burns push-in on the keyframe  ->  drop the scene
```

Warnings are recorded on the result and in `result.json`, so a degraded run is
visible rather than silent.

## Files

| File | Job |
|---|---|
| `enhancer.py` | Sharpens the take, picks a fixed style preset, and works out what is still worth **asking the user**. Runs before planning; every question has a default so silence is a valid answer. |
| `defaults.py` | Fills every missing input. Infers the sport, snaps duration to 15/30/60/90, replaces a too-short take, runs focus detection. Nothing downstream sees a null. |
| `focus.py` | Classifies the take: player / team / matchup / generic, from catalog mentions. Drives palette, venues and casting. |
| `catalog.py` + `catalog/` | Character & team catalog: real-player looks, team colour palettes, venues, AI reference stills. See `catalog/README.md`. |
| `catalog_build.py` | Generates catalog reference stills — with the SAME image model that renders keyframes. Explicit `--yes` before any spend. |
| `library.py` | Roster/venue access over the catalog, with nickname aliases, fuzzy lookup and a hard-coded fallback. An off-roster name still yields a renderable character. |
| `planner.py` | The script. Asks the model, **repairs** what comes back, falls back to a deterministic template, stamps team identity onto the cast. |
| `prompts.py` | Style bible and prompt builders for keyframes, motion and reference stills. |
| `prompt_registry.py` | One entry per prompt: purpose, stage, model. `python -m app.video.prompt_registry`. |
| `providers.py` | OpenAI (planning + review), OpenRouter (images, video), plus offline stubs for all of them. |
| `research.py` | Optional web search for off-catalog cast (`WEB_RESEARCH=openai`). Never fatal. |
| `review.py` | The cheap gate: inspects a keyframe before anything expensive happens. |
| `media.py` | ffmpeg. Ken Burns, loudness matching, concat, captions + disclosure burn-in, probing. |
| `runner.py` | Orchestration, per-scene retry, reference selection, cost ledger, DB wrapper. |
| `cli.py` | Run it without the API or a database. |

## Running it

```bash
cd backend
.venv/bin/python -m app.video.cli "Wemby still can't find Brunson" --tone Funny
.venv/bin/python -m app.video.cli "" --seconds 30          # missing input is fine
.venv/bin/python -m app.video.cli "lakers bad" --brief-only  # enhance + questions
.venv/bin/python -m app.video.cli "take" -i                # answer them interactively
.venv/bin/python -m app.video.cli "take" --plan-only       # just the script
.venv/bin/python -m app.video.cli "take" --raw             # skip enhancement
.venv/bin/python tests/test_video_workflow.py              # 50 robustness tests
```

Every argument is optional. With none at all it still writes an MP4.

## The enhancer, and what it asks

Quality is decided before any money is spent, so `enhancer.enhance()` runs
first. It sharpens the take through the language model ("lakers bad" →
"Every time the Lakers throw up a brick you can hear Shaq groaning"), then
returns `Question` objects for the gaps that measurably change the output:

| Asked when | Why it matters |
|---|---|
| the take is too thin to build beats from | biggest single quality lever |
| the model reports a genuine ambiguity | wrong subject for the whole video |
| a named person is not in the catalog | renders as a lookalike, not them |
| two teams and no clear lead | wrong palette for every scene |
| tone / length / look not stated | preferences we should not silently guess |

Nothing blocks. Every question carries a default, and `enhance()` with no
model, no answers and no catalog still returns a complete brief. Answers come
back through `apply_answers(brief, {...})`; the API can serialise
`brief.to_dict()` straight to a client.

**Style is a preset, not free text.** `STYLE_PRESETS` offers three
photographic looks (broadcast / cinematic / gritty). The planner used to
invent a style line per job, which is exactly how one video came out half
photoreal and half cartoon — free-form style is not repeatable.

## Turning generation on

Off by default — nothing here spends money until you say so.

```env
PIPELINE_MODE=real          # use this pipeline instead of the demo clip
OPENAI_API_KEY=...          # a real script instead of the template
IMAGE_PROVIDER=openrouter   # real keyframes, ~$0.05 each
VIDEO_PROVIDER=openrouter   # real animation, ~$0.14/second at 720p
```

Enable them one at a time. `IMAGE_PROVIDER` alone gives real-looking output
for pennies, since the keyframes are then animated locally.

## Four things the code encodes that are easy to undo by accident

**Name the person, and forbid the lettering.** Both, in every prompt. Removing
the name to suppress text also removes the likeness — an early render replaced
a recognisable player with a generic stand-in that way. Keeping the name but
dropping the wardrobe rule brings back garbled shirt text and brand boards.
`prompts.py` and the `library.py` wardrobe strings do this together;
`test_prompts_name_the_subject_and_forbid_lettering` guards it.

**Job style may only ADD to the style bible.** `style_for()` used to read
`plan.style or STYLE_BIBLE`, so a model-authored style line silently replaced
the bible — and with it the only mention of "photoreal". A scene rendered as
an isometric cartoon in the middle of an otherwise photographic video. The
`PHOTOREAL` clause is now separate, non-overridable, and opens *and* closes
every image and motion prompt; `safe_style()` strips medium words from
anything a model writes. `test_model_style_can_never_replace_the_photoreal_anchor`
guards it.

**No text-bearing props.** Newspapers, phones, screens, signs, whiteboards —
anything a camera would show writing on forces the image model to render
lettering, which is an automatic reject. The planner is told to avoid them and
`build_image_prompt` blanks any that slip through. This cost two consecutive
keyframe rejections in a real run.

**Consecutive scenes never share a speaker.** The generator gives the same
character a different voice in every clip, and that cannot currently be pinned.
Alternating speakers means no character is ever heard twice, so the drift has
nowhere to show. `planner._repair` enforces it and
`test_consecutive_scenes_never_share_a_speaker` guards it. If voice pinning
becomes available, this constraint can be relaxed — until then it is load-bearing.

## Not built yet

- Durable queue and a worker process. Generation still runs on a background
  thread, so a deploy mid-job loses it (BR-07).
- Per-asset provenance tables. Costs and prompts are written to the work
  directory, not the database.
- Object storage. Output lands on local disk.
- Catalog reference stills. The wiring exists end to end, but no images have
  been generated yet — run `python -m app.video.catalog_build --all --yes`
  (with `IMAGE_PROVIDER=openrouter`) when ready to spend ~$0.10 per character.
- Parallel scene generation. Scenes run sequentially; ~4 min for a 15s video.
