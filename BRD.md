# BanterClips — MVP Business Requirements

**Version:** 2.1 (2.0 simplified from v1.4 — same requirement IDs; the full
v1.4 narrative is archived. 2.1 adds the Bold tone and selectable duration) · **Product:** Web app · **Phase:** 1 — private beta

---

## 1. What we are building

Turn a written sports opinion into a finished **short cinematic vertical
video** (10–30 seconds, chosen by the user) — script, commentator voiceover,
AI scenes, captions — and let the user **publish it to social without
leaving the app**.

> One-line promise: *any sports take becomes a post-ready video, no editing.*

The MVP answers one question: **can we produce videos good enough, fast
enough, that creators publish them and come back for more?**

## 2. Target user

Independent sports creators who post short-form content at least weekly and
currently spend real time writing, voicing, and editing each clip.

## 3. MVP user journey

1. Visitor sees a pre-rendered example on the landing page → signs up.
2. New users get a short, fully skippable onboarding (interests, role,
   social connect, plan choice).
3. User types a take, picks a sport and a tone, hits generate.
4. User watches honest progress, then previews the finished video.
5. User publishes to their connected Instagram — or, on the paid plan,
   downloads the MP4.
6. Users at their monthly limit are offered the paid plan.

## 4. Requirements

Each requirement is satisfied when every bullet under it is true.

**BR-01 — Landing page**
- A visitor understands the product without scrolling, from a real
  pre-rendered example video (no live generation before sign-up).
- The page uses the client-provided design as-is.
- The primary button leads to sign-up.

**BR-02 — Accounts**
- Users can sign up and sign in with email + password (with verification
  email), with Google, or with an emailed magic link.
- A "forgot password" flow exists (also how Google users add a password).
- A user can only ever see their own videos and data.

**BR-03 — Creation input**
- Exactly four inputs: the take (10–280 characters), a sport
  (NBA / NFL / Soccer / MLB), a tone (**Funny / Savage / Hype / Bold**),
  and a video length (**10s / 15s / 30s**).
- Lengths above 15s are a paid-plan feature: visible to free users but
  locked, acting as an upgrade prompt.
- Invalid input is rejected before generation starts.
- Onboarding choices pre-fill defaults but are never required.

**BR-04 — Script quality**
- The generated script has a hook, the user's take, and a punchline, spoken
  within the chosen video length.
- The script never reverses the user's stated opinion.

**BR-05 — Voice**
- Characters deliver their own lines, lip-synced, in a voice style fitting
  the character.
- Speech is clear and synchronized with the captions.

**BR-06 — Video output**
- 9:16 vertical MP4, 1080×1920, matching the chosen length (10/15/30s),
  with burned-in animated captions.
- One curated cinematic style featuring real players and authentic kits as
  AI-generated parody; no real match footage or broadcast material is ever
  used.
- Every video carries an AI/parody disclosure on every plan.
- (How the video is produced is defined in the companion technical spec,
  not in this document.)

**BR-07 — Honest generation status**
- The user sees the real current stage; nothing is shown as done before it is.
- Leaving the page never loses a running job.
- A failed job offers a free retry and never consumes the allowance.

**BR-08 — Preview and plan-gated delivery**
- Every finished video plays in the browser on desktop and mobile.
- Free accounts can publish only; the download button is visible but locked
  and is the upgrade prompt.
- Paid downloads are watermark-free and identical to the preview.
- Past videos remain available to re-publish or re-download.

**BR-09 — Usage limits**
- Free: 5 successful videos per month. Creator: 30. Resets monthly;
  no credit packs.
- Only successful videos count — failures and retries are always free.
- Remaining allowance is always visible; at the limit, generation is blocked
  with an upgrade prompt.

**BR-10 — Content safety**
- Takes and scripts are checked; playful rivalry is allowed, hate/threats
  and protected-class abuse are not.
- No impersonated voices; no fabricated claims presented as news.

**BR-11 — Product analytics**
- The key funnel events are recorded (sign-up, generation started/finished/
  failed, preview, publish, download, upgrade), enough to evaluate §6.
- No user-facing dashboard.

**BR-12 — Data & privacy**
- Videos are private to their owner and never made public without consent.
- A user can request full deletion of their account, data, and media —
  including their billing identity.
- Retention period is disclosed before launch.

**BR-13 — Direct publishing**
- A user can connect one Instagram account via the official OAuth flow, and
  disconnect it at any time.
- Publishing is an explicit per-clip action with an editable caption —
  nothing ever posts automatically.
- Publish status is honest (uploading / published with a link to the live
  post / failed with a plain reason), runs in the background, and failed
  publishes retry free without regenerating.
- More platforms come later, one at a time; they are visible but locked.

**BR-14 — Onboarding**
- Up to five light steps: sports, teams/players, role, social connect, plan
  choice. Every step is skippable; onboarding never blocks creation.
- Progress is never lost (e.g. by the social-connect redirect).
- Shown once; editable later from the account page.

**BR-15 — Plans and payment**

| | Free | Creator — $9.99/mo (introductory) |
|---|---|---|
| Successful videos | 5 / month | 30 / month |
| Video length | Up to 15s | Up to 30s |
| Publish to Instagram | Yes — watermarked | Yes — no watermark |
| Download MP4 | No | Yes — no watermark |
| Watermark | Always | Removed (AI disclosure stays) |
| Render queue | Standard | Priority |

- Free is deliberately publish-only: every free clip on social carries the
  watermark and markets the product.
- Payment runs through Stripe Checkout; upgrade applies instantly;
  cancellation applies at the period end; videos are never deleted for
  billing reasons.
- A user can never be double-billed (at most one live subscription).

## 5. Business rules

1. Usage is charged only when a valid video is produced.
2. Failed jobs retry free.
3. The user's opinion is never silently reversed.
4. The watermark is removed only on the paid plan; the AI/parody disclosure
   is removed on no plan.
5. Videos are private to their owners.
6. All source media must have documented commercial-use rights.
7. Never promise virality, and never promise "seconds" until measured.
8. No internal social feed, ever.
9. Publishing is always an explicit user action through official APIs.

## 6. Success criteria (beta exit gates)

| Gate | Target |
|---|---|
| Generation reliability | ≥ 95% of jobs complete; median ≤ 5 min |
| Post-worthiness | ≥ 35% of finished videos are published or downloaded |
| Publishing adoption | ≥ 20% of active testers publish directly; ≥ 95% publish success |
| Retention | ≥ 25% of activated testers create another video within 7 days |
| Conversion | ≥ 5% of activated testers upgrade to Creator |
| Economics | Cost per accepted video below the approved ceiling; Creator margin positive |

The final test, in order: did the user get a valid video quickly · was it
good enough to publish or download · did they come back? If not, fix quality
— do not add features.

## 7. Out of scope for the MVP

Remix library and public videos · more than one social platform ·
scheduling and auto-posting · multiple voices/templates/lengths · credits,
annual billing, or plans beyond the two · feeds, comments, followers ·
teams, API, white-label · native mobile apps · live generation before
sign-up.

## 8. After the MVP (order of intent, gated on §6)

1. **Remix** — public library, counter/funnier/roast remixes.
2. **Distribution** — more platforms one at a time, then scheduling.
3. **Creator growth** — more voices/templates, brand kits, analytics.
4. **Teams, API, mobile** — only on proven demand.

## 9. Open items to close before public launch

1. Select and lock the video-generation provider (quality bake-off).
2. Meta app review, so any user can connect Instagram (longest lead time).
3. Confirm voice/music/asset licenses and the content policy.
4. Switch Stripe from test to live keys under the right business entity.
5. Set the beta retention period and recruit the tester cohort.
