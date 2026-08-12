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
.venv/bin/python -m app.video.cli "" --seconds 30        # missing input is fine
.venv/bin/python -m app.video.cli "take" --plan-only     # just the script
.venv/bin/python tests/test_video_workflow.py            # 23 robustness tests
```

Every argument is optional. With none at all it still writes an MP4.

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

## Two things the code encodes that are easy to undo by accident

**Name the person, and forbid the lettering.** Both, in every prompt. Removing
the name to suppress text also removes the likeness — an early render replaced
a recognisable player with a generic stand-in that way. Keeping the name but
dropping the wardrobe rule brings back garbled shirt text and brand boards.
`prompts.py` and the `library.py` wardrobe strings do this together;
`test_prompts_name_the_subject_and_forbid_lettering` guards it.

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
