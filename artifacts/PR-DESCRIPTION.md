# Video generation pipeline: real players, quality gates, durable queue

Implements `backend/VIDEO-GENERATION-PLAN.md`: a take becomes a 9:16 vertical
video with real player likenesses, gated on quality before any expensive step,
produced by a worker that survives deploys.

## The pipeline

`enhance → resolve → focus → plan → cast → keyframe → review → animate → assemble → validate`

Keyframe-first is the whole economic argument: a still costs $0.05, an 8s clip
$1.12. Every quality decision is made on the still; motion is only bought for
frames that already passed review.

A job always produces a video. Each stage degrades rather than failing. Only
two things are fatal: no ffmpeg, or not one usable scene.

## Defects found by rendering, and fixed

Each shipped a real bad video first; each now has a test.

| Symptom | Cause |
|---|---|
| A scene rendered as an isometric cartoon | `style_for()` read `plan.style or STYLE_BIBLE`, so a model-authored style **replaced** the bible, deleting the only mention of "photoreal" |
| Two keyframes rejected in a row, $0.10 burnt | The planner put newspapers and a tablet in the scene; image models garble lettering |
| Legs cut at mid-thigh, dead floor below | Our own instruction: "keep the lower quarter visually calm" — the model obeyed by ending the subject above it |
| Three-panel collage keyframe | A camera direction reading "wide shot, then a close-up" is a shot list |
| Captions broke ffmpeg (`No such filter: '7.75'`) | An ASCII apostrophe terminated drawtext's quoted string; commas in `enable=between(t,a,b)` became filter separators |
| Paying customer downloaded the wrong video | `download_clip` returned `demo.mp4` unconditionally |
| Live status flickered empty | Progress lived in process memory; the API runs 2 workers |

## Production

- **Durable queue** — work is a row; a separate worker claims it with
  `FOR UPDATE SKIP LOCKED`. Deploy-safe, one job per clip, stale locks
  reclaimed. Graceful shutdown returns an unfinished job without counting an
  attempt. Verified by SIGTERM mid-render.
- **Storage** — one interface, local disk for dev, Supabase for prod.
  Artifacts tiered by lifetime: ~14 MB kept per clip, ~38 MB expired.
  Deleting a clip deletes its bytes.
- **Provenance** — cost, plan source, cast, per-scene review verdicts and
  model versions on the clip row, because the useful questions are queries.
- **`[mock]` in a take** simulates a run anywhere including production:
  stripped from the stored take, consumes no allowance, cannot be published.
- **Housekeeping** purges scratch and releases clips stranded by a deploy.

## Testing

76 tests: 56 workflow, 12 production, 8 queue. Verified against a running
two-worker API with a separate worker process.

## Before merging

- Create a public `clips` bucket in Supabase, set `SUPABASE_SERVICE_KEY`
  (the repo carries only the anon key, deliberately)
- Set `QUEUE_MODE=postgres`, install `banterclips-worker.service`
- `apt-get install ffmpeg` on the droplet
