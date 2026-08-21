# BanterClips — Credit-Based Pricing

Version 1.0 · 2026-08-21 · Replaces the "5 videos / 30 videos" model in
BRD BR-09/BR-15 once approved.

---

## 1. Why credits

Today we sell "videos per month". That breaks in three ways:

1. A 10-second 720p video costs us ~$1.55 and a 30-second 1080p video costs
   us ~$7.75 — but both count as "1 video". Users are pushed to always pick
   the most expensive option because it costs them the same.
2. When a user runs out, their only option is "upgrade your plan" — which
   forces them onto a higher monthly price forever, just because they had
   one busy week.
3. Adding any new AI feature (enhance, re-roll a scene, remix) has no way
   to be priced.

Credits fix all three: every AI action costs credits in proportion to what
it costs us, users buy more only when they need more, and new features just
get a credit price.

This is also simply how the market works now — see §7.

## 2. The core rules (non-negotiable)

1. **One wallet.** Every user has one credit balance. All AI actions draw
   from it. We show credits only — never "videos left", never money left.
2. **Out of credits → top up, never upgrade.** When the balance is too low,
   the app shows exactly one path: "Top up credits". We never show "upgrade
   your plan" as the answer to an empty balance, we never move anyone to a
   higher plan, and a top-up never changes what they pay next month. The
   plan is a capability + allowance choice; credits are fuel.
3. **Failures are free.** Credits are reserved when a generation starts and
   only kept when it succeeds. A failed job releases the full reservation.
   Retries charge like a normal run (and refund the same way if they fail).
4. **Every video shows its receipt.** Each clip displays the credits it
   used, with its line items (video + any paid extras used on it).

## 3. What a credit is worth

**1 credit = $0.01 of face value.** (Same convention as Runway, Kling and
Pika — it keeps mental math easy: 500 credits ≈ $5.)

We price AI actions at roughly **2.5× our measured provider cost**, rounded
to friendly numbers. That yields a ~35–40% gross margin after payment fees —
sustainable, and it means when provider prices drop we widen margin or cut
credit prices, without ever changing what a credit is.

## 4. What things cost (launch price list)

Measured basis: $0.148/second at 720p, $0.256/second at 1080p (real
production clips), plus ~$0.10–0.15 of images/script per video.

### Video generation (the main spend)

| Length | 720p | 1080p |
|---|---|---|
| 10s | **250 credits** | **425 credits** |
| 15s | **375 credits** | **650 credits** |
| 30s | **700 credits** | **1,200 credits** |

### Everything else

| Action | Credits | Note |
|---|---|---|
| ✨ Enhance take (2 new angles) | **2** | per press |
| Caption suggestions + regenerate | **0** | free — helps publishing |
| Publish to Instagram | **0** | free — it's the product's point |
| Retry a failed video | **0 net** | see rule 3 |
| Download (Creator) | **0** | plan capability, not a credit item |

Internal cost split per video, for our own accounting (users see only the
total): script ~1% · scene images ~4% · animation+audio ~93% · review ~2%.
This split is why almost every future price derives from *seconds of video
generated*.

## 5. Plans, free credits, and top-ups

### Free (on signup)

- **500 credits, one-time.** Enough for 2 short videos or 1 mid-length one,
  with room for enhances. One-time (not monthly) so throwaway accounts
  can't farm free generations. Watermark on, 720p, up to 15s — unchanged.

### Creator — $9.99/month

- **1,100 credits added every month** (a 10% bonus over face value — the
  reason to subscribe rather than only top up).
- Capabilities: 1080p, 30s videos, watermark-free publishing, downloads,
  priority queue. Capabilities come from the plan; fuel comes from credits.
- **Rollover:** unused plan credits carry over one extra month (HeyGen's
  model). Top-up credits never expire.
- Cancelling stops future monthly credits; the remaining balance stays
  spendable.

### Top-ups (available to everyone, Free included)

| Pack | Credits | Bonus |
|---|---|---|
| $5 | 500 | — |
| $10 | 1,050 | +5% |
| $25 | 2,750 | +10% |
| $50 | 5,750 | +15% |

Top-ups are the only thing we offer when a balance runs out. A Free user
who tops up stays Free (their capability limits stay — 720p/15s/watermark);
a Creator who tops up stays on $9.99. No prompt, screen, or email ever says
"upgrade to get more credits".

## 6. What the user sees

- **Balance:** one number, in the header/credits bar: "⚡ 1,240 credits".
- **Before generating:** the price of the exact video they configured
  ("This video: 375 credits") so there are no surprises.
- **After generating:** the receipt on the clip — e.g.
  "Used 379 credits · Video 15s/720p 375 · Enhance ×2 4".
- **Never shown:** dollars remaining, videos remaining, our costs, or any
  upgrade nag tied to the balance.

## 7. How others do it (research, 2026)

| Platform | Model | Notes |
|---|---|---|
| Runway | credits/second, ~$0.01/credit | 5–12 credits/s depending on model tier |
| Kling | credits/second | 6–8/s at 720–1080p, 9–12/s with audio; $10/mo = 660 credits |
| Pika | monthly credit plans | $10/mo = 700 credits; 1080p 5s clip = 40 credits |
| HeyGen | plan credits + top-ups | top-ups at $0.05/credit (min $5); unused monthly credits roll one month; annual plans accrue all year |
| Luma | monthly credits | no rollover |

Takeaways we adopted: $0.01 face value and per-second pricing (Runway/
Kling), audio-inclusive generation priced higher than silent (Kling — ours
always includes audio), top-ups + one-month rollover (HeyGen). Takeaway we
deliberately rejected: pushing plan upgrades as the answer to an empty
balance.

## 8. Fitting future features into this system

One rule decides everything: **if it calls a paid model, it costs credits
(priced at ~2.5× our cost, rounded); if it's our own software, it's a plan
capability or free.** Never both for the same thing.

| Future feature | How it fits |
|---|---|
| Re-roll one scene | video price ÷ number of scenes (e.g. 125 credits for one scene of a 15s/720p video) |
| Remix an existing video (new script, reuse the look) | ~75% of a fresh video's price |
| "Enhance video" / polish pass | credits by seconds re-processed, same formula |
| More voices / delivery styles | free choice; a premium cloned-voice tier would be +10% on the video price |
| Upscale an old 720p video to 1080p | the price difference between the two tiers |
| New video models (multi-model routing) | each model gets its own credits/second rate — exactly how Runway prices tiers |
| Trending-topic suggestions | free (it drives generation volume) |
| API access | same credit prices, larger top-up packs with bigger bonuses |
| Teams | one shared wallet, per-member usage visible to the owner |

The Creator plan stays lean on AI *inclusions* (it's an allowance + a
capability set). New AI features never get "unlimited on Creator" — they
get a credit price, so heavy users pay for what they use and the margin
can't go negative again (the old plan lost up to $60/user/month at full
usage).

## 9. Sanity check: margins at these prices

| Item | Price | Our cost | Gross margin |
|---|---|---|---|
| 10s 720p | $2.50 | ~$1.55 | ~38% |
| 15s 720p | $3.75 | ~$2.36 | ~37% |
| 30s 720p | $7.00 | ~$4.38 | ~37% |
| 15s 1080p | $6.50 | ~$4.12 | ~37% |
| 30s 1080p | $12.00 | ~$7.76 | ~35% |
| Creator month, fully spent | $9.99 | ≤ ~$6.20 | positive in all cases |

Every row is margin-positive — the first pricing we've had where that's
true. Payment fees (~3%) and retries-we-eat (~5% of jobs) come out of the
margin above and still leave ~30%.

## 10. Migration from today's plans

- Free users: balance set to 500 credits minus 250 per video already used
  this month (floor 0).
- Creator subscribers: 1,100 credits on their next billing date; plan price
  unchanged. Their old "30 videos" wording disappears from the UI.
- Comped accounts (beta testers): granted 1,100/month like Creator, marked
  comped, no billing.
- BRD updates needed on adoption: BR-09 (limits → credits), BR-15 (plan
  table), §5 business rule 1 (usage charged per successful *generation*,
  measured in credits).

## 11. Open decisions before build

1. Confirm the four top-up pack sizes and bonuses (§5).
2. Rollover: one month (proposed) vs none — one month is friendlier and
   costs little.
3. Whether Free gets a small monthly trickle (e.g. 100 credits) after the
   one-time 500 — good for retention, small farming risk. Proposed: revisit
   after abuse controls (the blocklist plus a device/IP check) are in.
4. Stripe mechanics: top-ups as one-time Checkout payments (new products),
   subscription unchanged at $9.99.

---

### Sources

- [Apiframe — AI video API pricing 2026](https://apiframe.ai/blog/ai-video-api-pricing-2026)
- [Rangy — AI video pricing explained](https://rangy.ai/blog/ai-video-pricing-explained/)
- [UlazAI — Runway/Kling/Luma/Pika comparison](https://ulazai.com/ai-video-models-guide-2025/)
- [eesel — HeyGen pricing](https://www.eesel.ai/blog/heygen-pricing)
- [HeyGen Help — credit-based plans](https://help.heygen.com/en/articles/15125761-heygen-credit-based-pricing-plans-explained)
- [HeyGen — pricing page](https://www.heygen.com/pricing)
- Internal: `UNIT-ECONOMICS.md` (measured per-second costs from production clips)
