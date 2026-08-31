# BanterClips — Pricing (MVP)

Version 2.0 · 2026-08-23 · Rewritten around the client's pricing & economics
feedback doc ("BanterClips Update — Feedback"), scoped to **current MVP
features only**: two plans (Free, Creator), 720p/1080p, 10/15/30-second
videos, enhance, script approval, Instagram publishing. Replaces v1.0.

---

## 1. The model in one paragraph

BanterClips is a **subscription + credits** business. The plan buys
*capabilities* (resolution, length, watermark-free, downloads, queue
priority) and a monthly credit allowance; **credits are the fuel** every AI
action burns. We never sell or display "videos per month" — a 10-second
720p clip and a 30-second 1080p clip differ ~5× in what they cost us, so
"1 video" is not a unit. Credits are, and when models get cheaper (the AI
router on the roadmap), the same credit prices simply buy us better margin —
no pricing redesign needed.

## 2. Core rules (non-negotiable)

1. **One wallet, credits only.** Every user has one credit balance. We show
   credits — never dollars, never "videos left", never our costs. A credit
   is an internal compute unit; we do not publicly state what it costs us.
2. **Out of credits → top up, never upgrade.** The only path shown for an
   empty balance is "Top up credits". No screen, prompt, or email ever says
   "upgrade your plan to get more credits". A top-up never changes the
   monthly price. Plans are capability choices; credits are fuel.
3. **You only pay for success.** The balance is checked up front, but the
   single charge happens only when the finished video lands. Failures,
   pauses (provider outage — progress saved, resume free) and abandoned
   scripts never touch the wallet, and a video can never be charged twice.
4. **Every video shows its receipt.** Each clip permanently displays how
   many credits it used and where they went, line by line (video + any
   paid extras used on it). The user can always answer "what did this
   video cost me and why" from the clip itself.
5. **Credit prices are admin-tunable.** Per-action credit costs live in
   config the admin panel can change (per model, per feature) without a
   release — the feedback doc's requirement, and how the router lands later
   without repricing.

## 3. What a credit is

A **Banter Credit** is an abstract unit of AI compute. Internal anchors
(never user-facing):

- **Today (MVP, single video model):** 1 credit ≈ **$0.04 of AI cost**.
  This is measured, not aspirational — see §9.
- **Target (after multi-model routing):** 1 credit ≈ $0.02 of AI cost,
  which is where the feedback doc's 85% margin goal becomes reachable.

Retail value of a credit ranges **$0.065–$0.127** depending on how it was
bought (big pack → plan/small pack). Prices below are set so every action
is margin-positive even at the cheapest pack rate.

## 4. Credit price list (MVP)

The rule everything derives from: **Standard (720p) = 4 credits/second,
HD (1080p) = 7 credits/second.** Script, live-context research, keyframes,
animation, and audio are all baked in — one number per video.

### Video generation

| Length | ⚡ Standard (720p) | ✨ HD (1080p) |
|---|---|---|
| 10s | **40 credits** | **70 credits** |
| 15s | **60 credits** | **105 credits** |
| 30s | **120 credits** | **210 credits** |

HD and 30s require the Creator plan (capability, not price).
We use the mode names **Standard / HD** in the UI, not raw resolutions —
so future model tiers (Cinematic, Ultra) slot in without relabeling.

### Everything else

| Action | Credits | Note |
|---|---|---|
| ✨ Enhance take (2 new angles) | **1** | per press |
| Script writing + approval + edits | **0** | included in the video price |
| Regenerate script with feedback | **0** | capped at 10 rounds per clip |
| Caption suggestions + regenerate | **0** | helps publishing |
| Publish to Instagram | **0** | it's the product's point |
| Retry a failed video | **0 net** | rule 3 |
| Download (Creator) | **0** | plan capability |

## 5. Plans (MVP: only these two)

### Free — $0

- **60 credits, one-time on signup** — exactly one 15-second Standard
  video (the full wow: script approval, real context, audio), or a
  10-second one with credits left for enhances.
- One-time, not monthly, so throwaway accounts can't farm generations
  (feedback doc's rule). Referral/promo/streak credits can be added later.
- Capabilities: Standard (720p) only, up to 15s, watermark on, no
  downloads, standard queue.
- Free users **can top up** — top-ups buy fuel, never capabilities: they
  stay 720p/15s/watermarked.

### Creator — $19/month

- **150 credits added every month.**
- Capabilities: HD (1080p), 30-second videos, watermark-free publishing,
  downloads, priority queue.
- **Rollover:** unused plan credits carry one extra month. Top-up credits
  never expire.
- Cancelling stops future monthly credits; the remaining balance stays
  spendable; capabilities revert to Free at period end.
- Annual (later, per feedback doc): $190/year ≈ 2 months free. Not in MVP.

## 6. Top-up packs (everyone, Free included)

| Pack | Credits | Price | Effective $/credit |
|---|---|---|---|
| Starter | 100 | **$12** | $0.120 |
| Creator Pack | 300 | **$29** | $0.097 |
| Pro Pack | 750 | **$59** | $0.079 |
| Studio Pack | 2,000 | **$129** | $0.065 |

Bigger packs are cheaper per credit; the smallest pack absorbs Stripe's
fixed fee (30¢ is 5.4% of $12 — a $5 pack would give fees ~9%, so no pack
below $12). Sold as one-time Stripe Checkout payments; subscription
unchanged.

## 7. What the user sees

- **Balance:** "⚡ 150 credits" in the header, with a dynamic estimate
  under it that follows the selected mode — "≈ 2 videos at 15s Standard",
  "≈ 1 video at 15s HD" (feedback doc §10; replaces "5 of 30 monthly
  videos left" everywhere).
- **Before generating:** the price of the configured video ("This video:
  60 credits") next to the generate button. This is **exact, not an
  estimate** — a fixed menu lookup on duration × mode. Internal retries,
  shot counts, or research never change it. Generation can't start
  without the full amount in the wallet.
- **After generating:** the receipt, kept on the clip forever — "Used 62
  credits · Video 15s Standard 60 · Enhance ×2 2". A successful video
  always charges exactly its quoted price; the total only grows by other
  itemized actions on that clip, each quoted exactly when used.
- **Never shown:** dollars remaining, videos remaining, our costs, model
  names, or any upgrade nag tied to the balance.

## 8. Every charging scenario, decided

| Scenario | What happens |
|---|---|
| Generation starts | balance checked against the exact quote; **nothing is charged** |
| Video completes | the quoted price is charged, once; receipt attached |
| Job fails | nothing was charged; retry is free |
| Provider runs out of credits mid-render | job **pauses** with the reason shown; finished scenes are checkpointed; resume is free and never re-bills them |
| User abandons at script stage (deletes clip / never approves) | nothing was charged; the few cents of script cost are ours |
| Script regenerated with feedback | free (cap 10); cost is ours, baked into video margin |
| Balance too low to start | one message, one button: price shown + "Top up credits" — never "upgrade" |
| Balance runs out mid-month (Creator) | same: top up; next month's 150 arrive on the billing date regardless |
| Free user tops up | stays Free — 720p/15s/watermark limits unchanged |
| Creator cancels | keeps balance, loses monthly drops + capabilities at period end |
| Provider balance empty on our side | preflight pauses the job before any scene renders — never a silently degraded video |
| Chargeback / refund | credits from that payment are clawed back (floor 0); account flagged for review |
| Blocked user | silent blocklist as built — no credit interaction |

## 9. Unit economics (measured, not assumed)

Measured production cost with the current single-model pipeline
(UNIT-ECONOMICS.md): **~$0.148/second at 720p, ~$0.256/second at 1080p**,
all-in (keyframes + animation + audio), plus ~$0.03 of script + live
context per clip. LLM work is economically irrelevant, exactly as the
feedback doc says — video generation is ~93% of the cost.

Margin per video at the two retail extremes (starter-pack rate $0.12/cr
vs biggest-pack rate $0.065/cr):

| Video | Credits | Our cost | Margin @ $0.12/cr | Margin @ $0.065/cr |
|---|---|---|---|---|
| 10s Standard | 40 | ~$1.58 | 67% | 39% |
| 15s Standard | 60 | ~$2.39 | 67% | 38% |
| 30s Standard | 120 | ~$4.41 | 69% | 43% |
| 10s HD | 70 | ~$2.69 | 68% | 40% |
| 15s HD | 105 | ~$4.15 | 67% | 39% |
| 30s HD | 210 | ~$7.79 | 69% | 43% |

Plan-level worst case (Creator burns all 150 credits on video): AI ~$6.00
+ Stripe ~$0.85 + infra ~$0.30 = **$7.15 → 62% gross margin**. Typical
months (partial utilization) land 70%+. Free user worst case: $2.39
one-time acquisition cost per signup.

**The honest gap vs the feedback doc:** the doc targets 85%+ margins,
which assume a blended ~$0.02/credit AI cost via multi-model routing
(70% cheap / 20% mid / 10% premium). On today's single premium-ish model
we are at ~$0.04/credit, so MVP floor margin is ~40–60%, not 85%. The
credit system is what makes the 85% reachable *without repricing*: when
the router (roadmap P2) lands, cheap routes cut COGS per credit roughly
in half and every table above improves in place.

## 10. Migration from today's plans

- Free users: balance set to **60 minus 40 per video already generated**
  (floor 0); "X of 5 videos" UI removed.
- Existing $9.99 Creator subscribers: **grandfathered at $9.99 with 75
  credits/month** until they cancel; new subscriptions are $19/150. (Open
  decision §12.1 — alternative is a 2-month courtesy at 150 then notify.)
- Comped/beta accounts: 150 credits/month, marked comped, no billing.
- BRD updates on adoption: BR-09 (limits → credits), BR-15 (plan table),
  §5 business rule 1 (usage = credits charged per successful generation).

## 11. From the feedback doc, deliberately deferred (not MVP)

Pro $49 / Studio $99 / Business $299 / Enterprise tiers · premium model
modes (Cinematic 🔥, Ultra 👑) and the AI router that powers them ·
reference photos ("put yourself in") · remix + Remix Library · Story Mode
and 45/60-second videos · annual billing · referral & streak credits ·
prompt-length gating by plan · scheduled publishing, analytics, teams,
Repurpose. Each already has its slot: new tiers add a price + credit pool;
new models add a credits/second rate; new features get a credit price
(if they call a paid model) or a plan capability (if they're our
software) — never both.

## 12. Open decisions before build

1. Grandfathering: $9.99/75cr forever vs 2-month courtesy at 150cr (§10).
2. Creator pool: keep the doc's 150, or 250 so one 30s HD video (210cr)
   fits inside a monthly pool without a top-up. Recommendation: keep 150 —
   a Creator wanting the maximum video topping up is the intended
   power-user mechanic, and the pool grows naturally when the router
   halves per-credit cost.
3. Free signup grant: 60 (one flagship 15s) vs 40 (one 10s, ~$1.60 CAC).
4. Whether the enhance charge (1cr) is worth the friction vs free-with-
   rate-limit. Proposed: charge — it's the doc's number and stops farming.

---

### Sources

- Client feedback doc: "BanterClips Update — Feedback" (Google Doc,
  pricing & economics tab, 2026-08) — credit system, plan prices, pack
  prices, router strategy, margin targets.
- Internal: `UNIT-ECONOMICS.md` (measured per-second production costs),
  `ADMIN.md` (credit-price config surface), `ROADMAP.md` (router = P2).
