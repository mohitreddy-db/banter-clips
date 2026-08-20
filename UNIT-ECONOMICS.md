# Unit economics — video generation

## Per-component pricing

| Component | Model | Listed online | What we actually pay (measured) |
|---|---|---|---|
| Scene keyframe (image) | x-ai/grok-imagine-image-quality | from $0.05/image | ≈ $0.05/image — matches |
| Scene animation (video) | x-ai/grok-imagine-video-1.5 | **from** $0.08/second | ≈ **$0.14/second at 720p** (the "from" price is the base tier; resolution raises it) |
| Script/plan | openai/gpt-4.1 | $2/M in · $8/M out | ≈ $0.01/clip |
| Keyframe review | openai/gpt-4o-mini | $0.15/M in · $0.60/M out | ≈ $0.001/clip — noise |

**Cost formula (720p):** `scenes × $0.05 + output_seconds × ~$0.14 + ~$0.01`

Two gotchas the formula hides:
- We are billed on **delivered** seconds, not requested: a "15s" clip renders
  16.1s, a "30s" renders 30.3s.
- A keyframe that fails review is retried (up to 3 attempts) — occasionally
  adds $0.05–0.10 to a clip. Retried *jobs* are free to the user but not to us.

## Measured cost per clip — 720p

| Duration (requested → delivered) | Scenes | Cost per clip (n) | Effective $/output-second |
|---|---|---|---|
| 10s → 10.2s | 2 | **$1.52–1.57** (n=4) | $0.151 |
| 15s → 16.1s | 2 | **$2.36–2.46** (n=7) | $0.148 |
| 30s → 30.3s | 3 | **$4.38** (n=2) | $0.145 |

Blended across all 13 clips: **$0.148 per output-second at 720p**. Remarkably
stable — the per-second rate barely moves with duration because the fixed
costs (keyframes + text) are small.

## 1080p — estimated, NOT yet measured

No 1080p clip has been generated yet. Working assumption ~2× the 720p video
rate (industry-typical for resolution doubling; xAI does not publish the
tier multiplier):

| Duration | 720p (measured) | 1080p (estimate) |
|---|---|---|
| 10s | $1.55 | ~$3.0 |
| 15s | $2.40 | ~$4.7 |
| 30s | $4.38 | ~$8.6 |

One paid test run (~$5) pins the real number. Until then treat 1080p margins
as unknown-but-worse. `MAX_JOB_COST_USD` is set to $14 to let a 30s 1080p job
finish under this assumption.

## Plan-level economics

### Free plan — 5 videos/month, 720p, ≤15s, $0 revenue

| Usage pattern | Monthly cost per user |
|---|---|
| 5 × 10s | $7.75 |
| 5 × 15s | $12.00 |

Every free user costs **$8–12/month**, recovered only via the watermark's
marketing value and conversion. This is the spend the (currently disabled)
daily cap existed to bound.

### Creator plan — $9.99/month revenue, 30 videos, up to 30s, 1080p allowed

| Usage pattern | Monthly cost | Margin |
|---|---|---|
| Break-even usage | ~$10 | ≈ 4 × 15s or 6 × 10s at 720p |
| 30 × 15s @ 720p | ~$71 | **−$61** |
| 30 × 30s @ 720p | ~$131 | **−$121** |
| 30 × 30s @ 1080p (est) | ~$258 | **−$248** |

A Creator turns unprofitable at their **5th video of the month**. The plan
only works if median paid usage stays low single-digits — which contradicts
selling "30 videos". This is the economics gate in BRD §6 (`Creator margin
positive`), currently failing on paper.
