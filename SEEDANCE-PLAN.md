# Seedance on OpenRouter — Unit Economics + Integration Plan

2026-08-31 · Companion to `UNIT-ECONOMICS-TABLE.md` and `ROADMAP.md:50`
(the P2 "multi-model routing" item — this is that plan). All prices
checked on openrouter.ai today. We stay OpenRouter-only: same API key,
same `/videos` endpoint, same `usage.cost` accounting we already use
for Grok Imagine.

## 1. What Seedance costs (OpenRouter, per second of output, 9:16)

Derived from OpenRouter token rates at 24fps (`tokens/s = W×H×24/1024`);
spot-checked against each model page's listed per-second price.

| Model (OpenRouter ID) | 480p | 720p | 1080p | Duration | Latency P50 |
|---|---|---|---|---|---|
| `bytedance/seedance-2.0-mini` ¹ | $0.013 | **$0.030** | — (720p max) | 4–15s | ~154s |
| `bytedance/seedance-1-5-pro` (no audio) | $0.012 | $0.026 | **$0.058** | 4–12s | ~105s |
| `bytedance/seedance-1-5-pro` (with audio) | $0.023 | $0.052 | $0.117 | 4–12s | ~105s |
| `bytedance/seedance-2.0-fast` | $0.040 | $0.091 | $0.204 | 4–15s | ~145s |
| `bytedance/seedance-2.0` | $0.067 | $0.151 | $0.340 | 4–15s | ~160s |
| `bytedance/seedance-2.5` | $0.103 | $0.231 | — (720p max) | 4–30s | ~343s |
| *today:* `x-ai/grok-imagine-video-1.5` | $0.080 | ~$0.10–0.12 | $0.250 | 1–15s | ~33s |

¹ Mini's $1.40/M-token rate carries a "60% discount" badge today. At
full rate it's ~$0.076/s at 720p — still under Grok. Don't build the
pricing page on the promo number.

All Seedance variants do image-to-video with first-frame control and
9:16 — exactly what `animate()` sends. Single provider ("Seed"),
89–96% 3-day availability, so the fallback path stays mandatory.

## 2. Unit economics if we route to Seedance

Picks: **2.0 Mini for Standard 720p**, **1.5 Pro (audio off) for HD
1080p**. Assumes non-video overhead (keyframes, planning, retries)
stays ~$0.03/s — the gap between our measured $0.148/s all-in and
Grok's video-only rate. Verify against `provenance` after the pilot.

- All-in 720p: ~$0.148/s → **~$0.06/s** · per credit $0.037 → **~$0.015**
- All-in 1080p: ~$0.256/s → **~$0.09/s** · per credit $0.037 → **~$0.013**

| What | Credits | User pays | Cost today | Cost on Seedance | Margin today → new |
|---|---|---|---|---|---|
| 15s Standard | 60 | $6.00 | $2.39 | **~$0.90** | 60% → **~85%** |
| 30s Standard | 120 | $12.00 | $4.41 | **~$1.80** | 63% → **~85%** |
| 15s HD | 105 | $10.50 | $4.15 | **~$1.35** | 60% → **~87%** |
| 30s HD | 210 | $21.00 | $7.79 | **~$2.64** | 63% → **~87%** |
| Free signup grant (60 cr) | — | $0 | ≤$2.39 | **≤$0.90** | 2.6× cheaper CAC |

At the worst pack rate ($0.065/cr) Standard margin goes **38–43% →
~77%**. This is the "path to 85%" row in `UNIT-ECONOMICS-TABLE.md`,
without touching a single price.

**The trade:** speed. Grok returns a scene in ~33s; Seedance takes
2–3 minutes (2.5: ~6). Scenes run in a threadpool so wall time ≈
slowest scene, but user-facing generation time roughly doubles.
That's the real cost of the 5× cheaper compute.

## 3. How it fits — multi-model routing

Today `VideoProvider` (`backend/app/video/providers.py:184`) already
POSTs the OpenRouter `/videos` body Seedance expects (`model`,
`prompt`, `duration`, `resolution`, `aspect_ratio`, `frame_images`
first-frame). Model choice is one global env var — no per-clip
routing. Plan:

**Phase 0 — pilot, zero code.** `VIDEO_PROVIDER=openrouter
VIDEO_MODEL=bytedance/seedance-2.0-mini` on a test clip. Known risk:
our duration clamp is `max(1, min(15, …))` (`providers.py:208`) but
Seedance's floor is **4s** — a short scene may 400. Acceptable for a
manual pilot.

**Phase 1 — model capability table (~30 lines).** In `providers.py`,
a small per-model dict: `{min_s, max_s, max_res, generate_audio}`.
Clamp duration per model (floor 4 for Seedance, cap 12 for 1.5 Pro),
send `generate_audio: false` explicitly (it defaults on and doubles
1.5 Pro's price; we add our own audio in ffmpeg anyway). Record the
model used in each scene's `provenance` asset entry
(`runner.py:569`) so admin cost reporting can split by model.

**Phase 2 — the router.** New setting `VIDEO_MODEL_ROUTES`
(JSON, admin-overridable via `runtime_settings`, same pattern as
`credit_prices`):

```json
{"720p": "bytedance/seedance-2.0-mini",
 "1080p": "bytedance/seedance-1-5-pro",
 "short_scene": "x-ai/grok-imagine-video-1.5",
 "fallback": "x-ai/grok-imagine-video-1.5"}
```

`video_provider(resolution)` (`providers.py:295`) already takes
resolution — make it consult the routes instead of the single
`VIDEO_MODEL`. Scenes under 4s route to `short_scene`. On submit
failure or timeout, retry once with `fallback` before the existing
Ken Burns degrade (`runner.py:393`). Call site (`runner.py:360`)
unchanged. Spend guardrails (`_Ledger`, daily cap, `usage.cost`)
work as-is since cost still comes back from OpenRouter per job.

**Phase 3 — prompt dialect.** `shotwriter.py:41` names Veo/Sora/Kling
and `build_motion_prompt()` (`prompts.py:358`) is tuned for
Grok/Veo. Add a Seedance variant — it favors explicit camera-move
language and handles multi-shot descriptions well.

**Phase 4 — rollout.** Route a % of Standard 720p jobs via a
`runtime_settings` toggle, compare cost/video and failure rate in
the admin costs panel (`admin_console.py:779`), then flip the
default. Keep Grok as `fallback` permanently.

**Later, optional:** OpenRouter `callback_url` webhooks instead of
8s polling (matters more at Seedance latencies); `seedance-2.5` for
single-pass 4–30s clips (one coherent take instead of stitched
scenes — pricier per second, but no seams); 1.5 Pro's native audio +
multilingual lip-sync for the dialogue-anchor scenes in
`VIDEO-REALISM-PLAN.md` step 8.

## 4. Decisions to make

1. Accept ~2× slower generation for ~5× cheaper compute on the
   default tier? (Recommended: yes, and route "fast" retries to Grok.)
2. Pilot budget: one Standard + one HD clip ≈ **$2.50 total** at
   current caps — well inside `MAX_JOB_COST_USD`.
3. Re-price later or bank margin now? Recommended: bank it — the
   table above hits 85% at today's prices.
