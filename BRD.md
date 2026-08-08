# BanterClips — MVP Business Requirements Document

**Version:** 1.4  
**Status:** Draft for validation  
**Product:** Web application  
**Source:** BanterClips product conversation and existing MVP PRD. v1.2 adds direct social publishing to the MVP scope per stakeholder feedback (Aug 2026): the journey must close inside BanterClips — generate, then publish directly, not generate → download → post elsewhere. v1.3 adds a light four-step onboarding and simple two-plan pricing (Free / Creator) per stakeholder review of the reference prototype (Aug 2026). v1.4 locks the client-call non-negotiables (Aug 2026): (1) monetization baked in from day one — Free is publish-only with watermark and no downloads, making the free tier the marketing engine; Creator unlocks watermark-free download and publishing; (2) video quality is the second hard gate; (3) tone selector is Funny / Savage / Hype; (4) the landing page uses the client's slim-MVP design verbatim.

## 1. Executive Summary

BanterClips turns a written sports opinion into a finished 12–15 second cinematic vertical story with a short script, generic commentator voiceover, three AI-generated scenes, and timed captions.

The long-term product includes a public Remix Library, paid privacy, direct publishing, scheduling, analytics, teams, and mobile apps. The first release will not attempt to prove all of that. It will answer one business question:

> Can BanterClips produce a sports video quickly and consistently enough that creators want to publish or download it?

The MVP therefore covers only:

**sports opinion → generated video → preview → publish or download**

Direct publishing to one connected social platform is part of the MVP: the core USP is not only creating clips but closing the journey inside BanterClips, instead of generate → download → post manually elsewhere. Remixing, payments, multi-platform publishing and scheduling, analytics dashboards, and mobile apps move to later phases and are unlocked only after the core video reaches its quality and usage targets.

## 2. Business Problem

Sports creators and fans regularly have timely opinions but turning each opinion into a publishable short video requires writing, recording, editing, captioning, and formatting. This limits how often they can publish and causes time-sensitive ideas to expire before they become content.

Generic AI video and editing products can perform parts of this workflow, but they still require the user to assemble the result and are not designed around short, opinionated sports commentary.

## 3. Product Opportunity

BanterClips can reduce a multi-tool editing workflow to a single prompt and provide a repeatable format for sports hot takes. If the output is good enough to post without further editing, the product can later monetize creation volume, privacy, branding, remixing, and distribution.

The opportunity is not validated by account registrations or generated scripts. It is validated when users publish or download videos and return to create more.

## 4. Product Positioning

**One-line promise:** Turn any sports opinion into a cinematic, post-ready vertical story without editing.

**Category:** AI sports content creation studio.

**BanterClips is:**

- A fast creation tool for short sports opinions.
- A web application that produces post-ready MP4 videos.
- A direct route from take to published post on a connected social account.
- Eventually, a searchable source library for creating remixes.

**BanterClips is not:**

- A social network or content feed.
- A general-purpose video editor.
- A source of unlicensed match footage.
- A replacement for TikTok, Instagram, YouTube, or X.

## 5. Target Customer

### 5.1 MVP primary customer

Independent sports creators who publish short-form content at least weekly and currently spend time writing, voicing, captioning, or editing each clip.

They are the best first customer because they can judge output quality, have an immediate publishing need, and can provide repeat-use data.

### 5.2 Later customers

- Sports podcasters producing social snippets.
- Team and fan-page administrators.
- Sports media social teams.
- Casual fans without editing skills.
- Agencies managing multiple sports brands.

The MVP will not build separate workflows for these later segments.

## 6. Business Objectives

### 6.1 MVP objectives

1. Validate that users will publish or download AI-generated sports videos.
2. Validate that users return to generate a second video.
3. Validate that creators will connect a social account and publish directly from BanterClips.
4. Establish the real cost, latency, and failure rate of the video pipeline.
5. Identify which script, voice, caption, and visual qualities block posting.
6. Measure conversion to a simple paid plan.
7. Build a small base of creator testers for the Remix Library phase.

### 6.2 Non-objectives for MVP

- Maximizing registrations or traffic.
- Launching a full pricing ladder.
- Building network effects.
- Supporting every sport, voice, template, and video format.
- Multi-platform publishing matrices, scheduling, or auto-posting.
- Serving teams or enterprise customers.

## 7. Core Business Hypotheses

| ID | Hypothesis | Validation signal |
|---|---|---|
| H1 | A typed sports opinion can become a post-worthy video without manual editing. | At least 35% of completed videos are published directly or downloaded. |
| H2 | Speed is materially better than the user's current workflow. | Median successful Quick Take finishes within 5 minutes; P95 is under 10 minutes. |
| H3 | The output creates repeat value, not novelty-only use. | At least 25% of activated testers generate another video within 7 days. |
| H4 | The service can support viable margins. | Cost per accepted Quick Take remains below the ceiling approved after the provider bake-off, including retries. |
| H5 | A narrow preset produces better results than many controls. | At least 70% of testers rate downloaded output 4/5 or higher for usability. |
| H6 | Direct publishing closes the broken generate → download → post-elsewhere journey and is preferred over manual posting. | At least 20% of activated testers connect a social account and publish at least one clip directly; publish success rate is at least 95%. |
| H7 | A simple paid plan converts at beta scale. | At least 5% of activated testers upgrade to Creator during the beta. |

These thresholds are launch gates, not market facts. They should be revised using actual beta data.

## 8. MVP Definition

### 8.1 MVP user journey

1. Visitor sees a pre-rendered example on the landing page.
2. Visitor signs in using one supported method.
3. A new user completes a light four-step onboarding — sports, favorite teams and players, role, and an optional social connect. Every step can be skipped and never blocks creation.
4. User enters a sports opinion.
5. User selects a supported sport and tone (pre-selected from onboarding where possible).
6. User starts generation.
7. BanterClips creates the script, voiceover, captions, and video.
8. User sees honest stage progress while the job runs.
9. User previews the completed video.
10. User publishes the clip to a connected social account (connecting it first if needed), downloads the MP4 (Creator plan only), or generates another version.
11. User sees honest publish status and can retry a failed publish without regenerating the video.
12. A user who reaches the monthly free allowance can upgrade to the Creator plan from the pricing page.
13. User can reopen recent completed videos.

### 8.2 MVP screens

- Landing page with value proposition, pre-rendered demo, and create CTA.
- Sign-in screen.
- Onboarding: four light, individually skippable steps — sports interests, favorite teams and players, intended role, and the optional social connect. Selections only pre-fill Studio defaults and example takes; there is no feed or recommendation system behind them.
- Create Studio containing input, generation status, result with publish (all plans) and download (Creator only) actions, and recent clips.
- Social account connect flow (OAuth): onboarding step four, also reachable from the result step and the account view, plus a publish-status state on the result. Skipping never blocks creation; additional platforms appear as visible-but-locked options.
- Plans & pricing page with the two plans and Stripe checkout for the Creator upgrade.
- Minimal account/usage view, including connected accounts and the current plan.

No separate dashboard, analytics area, library, or billing center beyond the single pricing page is required. Publishing lives inside the Create Studio result step, not in a separate publishing area.

## 9. MVP Business Requirements

### BR-01 — Immediate product demonstration

The landing page must show the finished product before registration using a pre-rendered BanterClip. It must explain the three-step workflow: enter a take, generate, download.

**Acceptance criteria:**

- A new visitor can understand the product without scrolling.
- The demo does not trigger paid generation or require a live fake workflow.
- The primary CTA opens sign-in or the Create Studio.
- The landing page implements the client-provided slim-MVP design as-is; it is not reinterpreted.

### BR-02 — Minimal account access

Users must have an account so usage can be limited and completed videos can be recovered. The MVP will support one authentication method already easiest in the chosen stack, preferably email magic link.

**Acceptance criteria:**

- A user can sign in and sign out.
- A user can access only their own generated videos.
- Session failure does not expose another user's content.

### BR-03 — Narrow creation input

The Create Studio must ask for only the information required to produce a useful result.

**Inputs:**

- Sports opinion: required, 10–280 characters.
- Sport: NBA, NFL, Soccer, or MLB.
- Tone: Funny, Savage, or Hype (client non-negotiable — the user picks the energy of the banter before generating).

Hot Take is the fixed MVP content type. Length, voice, and visual template are not user-selectable.

**Acceptance criteria:**

- Invalid or empty input is rejected before generation.
- The user can submit the form without completing onboarding.
- One action starts one generation job.

### BR-04 — Post-ready script

The system must transform the opinion into a short script with a hook, clear take, and ending punchline. The spoken duration, not a nominal word count, is the hard constraint.

**Acceptance criteria:**

- The final voiceover fits within 12–15 seconds.
- The script preserves the user's original position unless generation is explicitly retried.
- The script avoids generic introductions, long explanations, and fabricated statistics.

### BR-05 — Single high-quality voice treatment

The MVP must use one licensed, generic sports-commentator voice. It must not imitate a real commentator, athlete, or celebrity.

**Acceptance criteria:**

- Speech is intelligible and synchronized with captions.
- Voice usage is covered by the provider's commercial terms.
- A failed voice generation does not consume the user's allowance.

### BR-06 — Single cinematic visual format

The MVP must produce the three-scene cinematic Quick Take defined in the companion technical spec (VIDEO-PIPELINE-SPEC.md) rather than a template marketplace.

**Output standard:**

- 9:16 vertical MP4.
- 1080 × 1920 resolution.
- 12–15 second duration.
- Three generated story scenes in one curated cinematic sports-parody style.
- Fictional, generic, or properly licensed characters only.
- Animated, burned-in captions within mobile safe areas.
- BanterClips watermark.

The MVP must not use unlicensed match footage, team logos, broadcast graphics, or player likenesses. If a generated scene cannot be delivered after its bounded retry, the approved keyframe may use a deterministic pan/zoom fallback.

### BR-07 — Honest generation status

The user must see the actual current stage: planning story, creating voice, designing characters, generating scene images, animating scenes, assembling video, validating, or failed.

**Acceptance criteria:**

- The UI does not claim a stage completed before the backend confirms it.
- The user may leave and return without losing a running job.
- A failed job presents a retry action and does not reduce remaining usage.

### BR-08 — Preview and plan-gated delivery

Every successful job must end in an in-browser preview. Delivery is plan-gated: Free accounts publish the clip through BanterClips (watermarked); downloading the MP4 is a Creator-plan feature (watermark-free).

**Acceptance criteria:**

- The preview plays on current desktop and mobile browsers.
- Creator downloads contain the same video shown in preview, without the watermark.
- On Free, the download action is visible but locked and is the primary upgrade prompt.
- Users can return to their recent completed clips and publish or (on Creator) download again while retained.

### BR-09 — Usage control and plan allowances

The Free plan includes five successful generations per month; the paid Creator plan raises this to thirty per month (BR-15). There is no credit store; allowances reset monthly.

**Acceptance criteria:**

- Only successful completed videos count against the allowance; failed jobs and retries never do.
- Remaining usage and the current plan are visible before generation.
- Users at the Free limit see an upgrade prompt for the Creator plan and can alternatively request more beta access.
- Downgrades and cancellations take effect at the end of the billing period and never delete videos.

### BR-10 — Content and abuse safeguards

The product must protect users and the business without turning the MVP into a full moderation platform.

**Acceptance criteria:**

- Inputs and generated scripts are checked for disallowed hateful, sexual, violent, or targeted abusive content.
- Generic playful sports rivalry is permitted; protected-class abuse and credible threats are not.
- The system does not generate impersonated voices or present fabricated facts as verified reporting.
- Obvious automated quota abuse can be blocked.

### BR-11 — Minimum product analytics

The MVP must record only the events needed to evaluate the hypotheses.

**Events:**

- Landing CTA selected.
- Generation started.
- Generation completed or failed.
- Preview played.
- Video downloaded.
- Social account connected or disconnected.
- Publish started.
- Publish succeeded or failed.
- Another generation started.
- Onboarding step completed or skipped.
- Pricing page viewed.
- Upgrade started and completed.
- Waitlist or access request submitted.

Analytics must not require a user-facing dashboard.

### BR-12 — Data handling

MVP videos remain private to the creating account. They must not be made public retroactively when the Remix Library launches without user consent.

**Acceptance criteria:**

- Each stored video has an owner and visibility state.
- Signed media access expires or otherwise prevents unrestricted private access.
- A beta user can request deletion of their account and generated media.
- Retention duration is disclosed before launch.

### BR-13 — Direct social publishing

The MVP must let a user connect at least one supported social platform and publish a completed clip without leaving BanterClips. This closes the currently broken journey — generate in one tool, download, then post manually elsewhere — and is part of the core USP.

**Scope:**

- One platform at MVP launch. Candidates: Instagram Reels, LinkedIn, or X — selected before build based on target-cohort usage and platform API approval timelines.
- A second platform is added only after the first is reliable.
- A short caption can be reviewed and edited before publishing.
- No scheduling, no cross-posting to multiple platforms at once, no auto-posting.

**Acceptance criteria:**

- A user can connect and disconnect a social account via the platform's official OAuth flow; tokens are stored securely and are revocable.
- Publishing is an explicit per-clip user action; nothing is ever posted automatically.
- The published video is identical to the downloadable MP4, including watermark and AI/parody disclosure.
- The UI shows honest publish status: uploading, published (with a link to the live post), or failed with a plain-language reason.
- A failed publish can be retried without regenerating the video and never consumes generation allowance.
- If platform API approval is still pending at launch, the product ships download-first for that platform and enables publish when approval lands, without UI redesign.
- Publishing respects the platform's terms; no scraping, no reverse-engineered endpoints.

### BR-14 — Light onboarding and personalization

After first sign-in, the product shows a four-step onboarding: sports interests, favorite teams and players, intended role, and the optional social connect (BR-13). Its only job is to warm up the Studio and segment beta testers.

**Steps:**

1. "What sports are you into?" — multi-select; the four MVP sports are selectable, other sports are shown as visible-but-locked ("soon").
2. "Favorite teams & players" — free-text search with removable tags; optional.
3. "How will you use BanterClips?" — single-select role: Sports Fan, Creator, Podcaster, Media Company, Fantasy Creator.
4. "Connect your accounts" — the BR-13 connect prompt; explicitly optional.

**Acceptance criteria:**

- Every step is individually skippable and onboarding never blocks video creation.
- Selections pre-fill the Studio sport chip and example takes; they do not create a feed, recommendations, or notifications.
- Role and sport selections are recorded for beta segmentation analytics (BR-11).
- Onboarding is shown once; it is re-accessible from Account but never forced again.

### BR-15 — Simple two-plan pricing

The MVP offers exactly two plans through Stripe. Pricing stays deliberately simple until real per-video cost is measured (§12.3).

| | Free | Creator — $9.99/mo (introductory) |
|---|---|---|
| Successful videos | 5 / month | 30 / month |
| Publish to connected platform | Yes — with watermark | Yes — no watermark |
| Download 1080×1920 MP4 | No — publish-only | Yes — no watermark |
| BanterClips watermark | Always | Removed |
| Render queue | Standard | Priority |
| New platforms & features | — | First access |

The Free tier is deliberately publish-only (client non-negotiable): every free clip posted to social carries the BanterClips watermark, turning each free user into a distribution channel for the product.

**Acceptance criteria:**

- One pricing page shows both plans with a feature comparison; Stripe Checkout handles payment, receipts, and cancellation.
- Free accounts cannot download; the locked download action links directly to the Creator upgrade.
- Upgrading applies instantly; downgrading applies at period end; videos are never deleted for billing reasons.
- The AI/parody disclosure remains on all output regardless of plan; only the BanterClips watermark is removed on Creator.
- The introductory price is revisited after the economic gate; the product must not promise grandfathered pricing, and the plan must not be sold at negative gross margin.

## 10. MVP Scope Summary

### Included

- Benefit-led landing page with a real pre-rendered example.
- One sign-in method.
- Light four-step skippable onboarding.
- Opinion, sport, and tone input.
- One script format, voice, visual style, and output format.
- Real asynchronous generation stages.
- Preview, download, retry, and recent clips.
- Connect one social account and publish directly with caption, honest status, and retry.
- Free (5/month, publish-only, watermarked) and Creator ($9.99/mo, 30/month, downloads + no watermark, priority queue) plans with Stripe checkout.
- Basic safeguards and product analytics.

### Excluded

- Live pre-signup generation.
- Remixing and the public Remix Library.
- Public videos and creator profiles.
- More than one connected platform at launch; additional platforms follow one at a time.
- Scheduling, auto-posting, cross-posting matrices, and automated platform-specific caption/hashtag generation.
- Credits, add-ons, annual billing, and any plan beyond Free and Creator.
- Multiple voices, templates, lengths, and advanced editing.
- Trending topics, virality scoring, and recommendations.
- Deep personalization: feeds, recommendations, or content tailored beyond Studio defaults and example takes.
- Likes, comments, followers, messaging, or a feed.
- Brand kits, bulk generation, teams, APIs, and white label.
- Native mobile applications.

## 11. Business Rules

1. A generation is charged against usage only after a valid MP4 is produced.
2. Failed jobs may be retried without using additional allowance.
3. The user's opinion is the source intent; the generated script must not silently reverse it.
4. Free-plan output is publish-only and always carries the BanterClips watermark; the Creator plan unlocks downloads and removes the watermark, but never the AI/parody disclosure.
5. MVP videos are private to their owners.
6. Source media must have documented commercial-use rights.
7. The product must not promise that content will become viral.
8. The product must not promise generation “in seconds” until measured performance supports it; Quick Take targets a median under 5 minutes.
9. No feature may create an internal social feed.
10. Publishing is always an explicit per-clip user action through official platform APIs; BanterClips never posts automatically and never removes the AI/parody disclosure on published output.

## 12. Success and Release Gates

### 13.1 Operational gate

- At least 95% of accepted generation jobs complete successfully.
- Median Quick Take generation time is 5 minutes or less and P95 is under 10 minutes.
- Completed output consistently meets the required dimensions and duration.
- At least 95% of publish attempts to a connected account succeed, or fail with a clear, recoverable error.
- No known cross-account media access issue exists.

### 13.2 Customer-value gate

- At least 35% of completed videos are published directly or downloaded.
- At least 20% of activated testers publish at least one clip directly from BanterClips.
- At least 25% of activated testers create another video within 7 days.
- At least 70% of testers who publish or download rate the result 4/5 or higher for post-readiness.
- Paid conversion is measurable, targeting at least 5% of activated testers upgrading to Creator.
- Qualitative interviews identify no single repeated quality blocker across a majority of testers.

### 13.3 Economic gate

- Average accepted-video cost is at or below the ceiling approved after the provider bake-off.
- Creator-plan gross margin is positive at the measured cost per accepted video.
- Failure and retry costs are measured separately.
- Storage and retention costs are understood before opening access broadly.

Phase 2 should not begin until the customer-value gate is met. Reliability and cost improvements may continue in parallel.

## 13. Phased Product Roadmap

The phases are governed by evidence, not calendar dates.

### Phase 0 — Pipeline prototype

**Purpose:** Prove technical output quality with internal examples.

**Deliver:** Opinion-to-MP4 pipeline, one voice, one character/reference workflow, three generated scenes, deterministic fallback/assembly, and a small reference set across the four supported sports.

**Exit gate:** The team can produce at least 20 representative videos with acceptable caption sync, no media-rights issue, and measured cost/latency.

### Phase 1 — MVP private beta

**Purpose:** Validate download intent and repeat creation.

**Deliver:** The exact MVP defined in this document.

**Exit gate:** Operational, customer-value, and economic targets in Section 12 are met with a meaningful creator test cohort.

### Phase 2 — Remix and plan expansion

**Purpose:** Validate whether existing clips create new generations and deepen monetization proven in the MVP.

**Deliver:**

- Searchable Remix Library; never an infinite social feed.
- New videos public by default with clear disclosure.
- Public/private video controls.
- Three remix actions: Counter, Funnier, and Roast.
- Parent-child lineage and remix count.
- Creator-plan expansion (limits, pricing, premium remix controls) informed by beta economics.

MVP beta videos remain private unless owners explicitly publish them.

**Exit gate:** Remix starts contribute a meaningful share of generations, paid conversion is measurable, and public-content moderation is supportable.

### Phase 3 — Expanded distribution

**Purpose:** Deepen the publishing the MVP started: more platforms and more convenience, once single-platform publishing is proven.

**Deliver:**

- Additional platforms beyond the MVP launch platform, added one at a time as each becomes stable.
- Platform-specific caption and hashtag drafts.
- Scheduling, only after immediate publishing is reliable across supported platforms.

**Exit gate:** Connected users publish successfully at an agreed reliability target across platforms and retain better than download-only users.

### Phase 4 — Creator growth tools

**Purpose:** Increase value for high-frequency creators.

**Candidate deliverables, selected by usage data:**

- Additional voices and visual templates.
- Brand kit and watermark controls.
- Download and publishing analytics.
- Trend-inspired prompt suggestions.
- Higher limits or usage-based add-ons.
- A second paid plan only if one plan no longer fits observed segments.

**Exit gate:** Usage supports clear segmentation and the added tools improve paid retention or revenue per user.

### Phase 5 — Teams, API, and mobile

**Purpose:** Expand to professional organizations and creator workflows after the web product is established.

**Candidate deliverables:**

- Team workspaces and roles.
- Approval workflows and multiple brands.
- Bulk generation.
- API and white-label export.
- Native or cross-platform mobile app focused on create, preview, and publish.

**Entry gate:** Proven demand from paying teams or clear evidence that mobile access is limiting creation frequency.

## 14. Monetization Approach

The MVP launches with exactly two plans and nothing else (BR-15):

- **Free — $0/month.** 5 successful videos per month, publish-only through the connected account, always watermarked, standard render queue. Free users cannot download — every free clip lives on social with the BanterClips watermark, making the free tier the product's marketing engine.
- **Creator — $9.99/month (introductory).** 30 successful videos per month, HD download and publishing without the watermark, priority render queue, first access to new platforms and features.

Stripe handles checkout, receipts, and cancellation. Only successful videos count against either allowance.

The $9.99 point is inherited from the earlier prototype ladder and must be re-validated once the economic gate (§12.3) reports true cost per accepted video — the plan must never sell at negative gross margin. Credits, add-ons, annual billing, agency and team tiers, and “unlimited” plans are deferred until usage patterns justify them. The reference prototype's four-tier ladder (Free / Creator / Creator Pro / Agency) is the long-term direction, not the MVP.

## 15. Key Risks and Mitigations

| Risk | Business impact | MVP mitigation |
|---|---|---|
| Output feels generic or “AI-made” | Users do not download or return. | One curated story style, one voice, and a 20-video quality benchmark before adding variety. |
| Generation is slow or unreliable | Users abandon before preview. | Honest stages, recoverable async jobs, latency and failure tracking. |
| Costs exceed assumptions | Paid plans cannot sustain margins. | Five-use cap and per-stage cost measurement. |
| Generated people, sports footage, or logos lack rights | Takedowns or legal exposure. | Use fictional/licensed characters, clean generative scenes, documented source rights, and AI/parody labeling. |
| Banter becomes harassment | Brand and safety risk. | Input/output checks and clear rivalry-content boundaries. |
| Vendor dependency | Outages or sudden cost changes. | Keep stored inputs and stage outputs recoverable; avoid vendor-specific promises. |
| Full-platform scope returns too early | Slow launch and poor learning. | Require phase exit gates before expanding scope. |
| Social API approval delays | MVP publish feature slips. | Register the developer app and start platform review at project start (longest lead time); ship download-first and enable publish per platform as approval lands; one platform at a time. |

## 16. Dependencies and Decisions Required Before Build

1. Run the 20-storyboard video-provider bake-off and select one scene-animation provider.
2. Confirm `gpt-image-2` or select one alternative reference/keyframe provider.
3. Confirm the existing TTS provider and voice have commercial usage rights.
4. Measure cost, latency, retry rate, and accepted-scene rate on representative clips.
5. License or create the MVP music, sound-effect, fallback-background, and brand assets.
6. Define the prohibited-content, likeness, and AI/parody-labeling policy.
7. Choose the beta video retention period.
8. Recruit a small cohort of active sports creators for validation.
9. Decide which analytics service or existing product telemetry will record the MVP events.
10. Select the MVP publish platform (survey the tester cohort: Instagram Reels vs LinkedIn vs X), register the developer app, and submit the platform's API/app review immediately — this is the longest external lead time in the plan.
11. Set up the Stripe account, Creator-plan product/price, and webhook handling for upgrades and cancellations.

## 17. Final MVP Test

The MVP is successful only when the answer to all three questions is yes:

1. Did the user receive a technically valid video quickly?
2. Was the video good enough that the user published or downloaded it?
3. Did enough users return to create another one?

If not, improve the script, voice, captions, visuals, publish flow, or rendering workflow. Do not compensate by adding Remix, more platforms, scheduling, analytics, billing tiers, or more screens.
