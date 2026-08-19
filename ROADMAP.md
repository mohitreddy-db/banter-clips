# BanterClips — Roadmap

Last updated 2026-08-19. Priorities mirror the planning board ([P1]/[P2]);
dates are targets, not promises. Gates refer to BRD §6 success criteria.

## Shipped — live in production today

- **Core loop**: take → sport/tone/length (10/15/30s) → real AI video
  (grok-imagine image+video, gpt-4.1 scripts, lip-synced character dialogue,
  burned captions + AI-parody disclosure) → preview → publish.
- **Quality options**: 720p all plans · 1080p Creator (per-clip choice).
- **Accounts**: email+password, Google OAuth, magic link, password reset
  (Resend-branded emails); skippable onboarding with preferences.
- **Instagram publishing**: official Business Login OAuth, background Reel
  publish with live status, auto token refresh.
- **Take enhancement**: ✨ two-angle variations; AI caption suggestions with
  regenerate; honest per-stage generation progress with elapsed time.
- **Plans & billing**: Free (5/mo, watermark, publish-only) · Creator $9.99
  (30/mo, 1080p, 30s, watermark-free downloads) — **live Stripe** checkout,
  webhooks, portal, convergent subscription sync, audit log.
- **Ops**: droplet + Caddy + systemd API/worker split, durable Postgres job
  queue, storage upload retries + local fallback, per-job ($14) spend cap,
  full-deletion script, logs runbook, unit-economics doc.
- **Legal/compliance**: /privacy + /terms, AI-parody disclosure on every
  video, account-chooser OAuth, Google brand verification in progress.

## Launch runway — Aug 19 → Aug 29

| Item | Target | Notes |
|---|---|---|
| Top up OpenRouter + re-arm daily spend cap | **Aug 19** | balance is negative; generation is down until this |
| Pricing/limits pass on Creator | **Aug 21** | unit economics: negative margin at >4 videos — decide new limits or price before promoting paid |
| [Discussion] Define the **"wow" factor** | **Aug 22** | one-sitting workshop: the single moment that makes a first-time user share; feeds the announcement copy |
| Google brand verification cleared | **Aug 25** | TXT + re-verification submitted; follow up |
| Statement descriptor + first live charge self-test | **Aug 25** | subscribe with real card → webhook → cancel/refund |
| [P1] **Plan launch + LinkedIn announcement** | **Aug 28** *(was Aug 17 — overdue, rescheduled)* | needs wow-factor + pricing settled; demo clip + landing polish |

## September — make it operable and self-feeding

| Item | Target | Notes |
|---|---|---|
| [P1] **BanterClips admin panel** | **Sep 1 – Sep 12** | users/plans/comps, clip & cost overview, spend caps, failed-job retry, delete-user — replaces SSH-and-SQL ops |
| [P1] **Trending topics + prompt suggestion engine** | **Sep 8 – Sep 26** | replaces the removed static examples with live sports storylines; feeds Studio suggestions and (later) notification hooks |
| Meta App Review submitted | **mid-Sep** | longest external lead time; unblocks public Instagram connect — needed before any real launch spike |

## October–November — widen the pipes (P2)

| Item | Target | Notes |
|---|---|---|
| [P2] **Multi-model routing for video generation** | **Oct** | provider bake-off (BRD §9.1) → route per job by cost/quality/duration; also the biggest cost lever (listed base tiers at ~$0.08/s vs our $0.14/s) |
| [P2] **Publishing beyond Instagram** | **Oct – Nov** | one platform at a time (BRD rule §8): TikTok or YouTube Shorts first — decide by where beta users already post |

## Later — gated on beta results (BRD §6 / §8)

In order of intent, unlocked only if retention + post-worthiness gates pass:

1. **Remix** — public library, counter/funnier/roast remixes of existing clips.
2. **Distribution** — remaining platforms, then scheduling.
3. **Creator growth** — more voices/templates, brand kits, analytics.
4. **Teams, API, mobile** — only on proven demand.

Standing candidates, unscheduled: Supabase custom auth domain ($10/mo consent-
screen polish) · UAT environment (branch domain + second service pair) ·
480p draft tier · credit-based pricing.

## Principles (carried from the BRD)

- Fix quality before adding features — the gates are reliability, post-rate,
  retention, positive Creator margin.
- One platform at a time; publishing is always explicit; no internal feed.
- Every video stays clearly AI-parody labelled, on every plan.
