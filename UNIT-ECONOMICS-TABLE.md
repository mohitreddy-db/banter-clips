# BanterClips — Unit Economics, One Table

2026-08-25 · The simple version. Full reasoning lives in `PRICING.md`
(prices) and `UNIT-ECONOMICS.md` (measured costs).

The two numbers everything hangs on:

- **1 credit sells for ≈ $0.10** — $0.065 in the biggest top-up pack,
  up to $0.127 as part of the Creator plan.
- **1 credit costs us ≈ $0.04** of AI compute today — measured
  ~$0.148/sec at 720p, ~$0.256/sec at 1080p, all-in.

| What | Credits | User pays (≈$0.10/cr) | Our cost | Margin |
|---|---|---|---|---|
| 1 credit | 1 | $0.10 | $0.04 | ~60% |
| 10s Standard video | 40 | $4.00 | $1.58 | 60% |
| 15s Standard video | 60 | $6.00 | $2.39 | 60% |
| 30s Standard video | 120 | $12.00 | $4.41 | 63% |
| 10s HD video | 70 | $7.00 | $2.69 | 62% |
| 15s HD video | 105 | $10.50 | $4.15 | 60% |
| 30s HD video | 210 | $21.00 | $7.79 | 63% |
| Enhance take | 1 | $0.10 | <$0.01 | ~95% |
| Creator month, all 150 spent | 150 | $19.00 | $7.15¹ | 62% |
| Free signup grant | 60 | $0 | ≤$2.39 | (acquisition cost) |

¹ AI $6.00 + Stripe $0.85 + infra $0.30. Typical months (credits not
fully spent) land 70%+.

**Range:** at the cheapest pack rate ($0.065/cr) video margins bottom
out at **38–43%**; at plan/starter rates they reach **~67%**. Every row
is positive today.

**Path to 85%:** the AI router (roadmap P2) cuts our cost per credit
from ~$0.04 toward ~$0.02, lifting every margin in this table without
changing a single price.
