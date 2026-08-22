# BanterClips — Admin Console (MVP scope)

Version 2.0 · 2026-08-22 · Companion to `PRICING.md` (credits) and the
existing `/admin` catalog page. Supersedes v1.0's flat 6-section panel.

Reference: the client's prototype console (Claude artifact
`6fb99753-d9c7-45b7-98af-5d9a37a8acfa`, "BanterClips admin panel
prototype") shows a ~30-section enterprise console. This doc keeps its
**information architecture** — a KPI dashboard where every widget is a
summary that drills into its own detail tab — and cuts the section list
to what the MVP's data can actually power. Figma frames 15–23 in the
"Phase 1 MVP" file implement this spec in the app's navy/cyan theme.

## 1. Principles

- **Summary → detail.** The Dashboard is the operating picture; every
  widget on it links to a tab that shows the full data behind it. No
  dead-end numbers.
- **One operator, real data.** Every widget reads from tables that exist
  (users, clips, jobs, events, catalog, Stripe) — no vanity metrics.
  Sample numbers in designs use realistic MVP scale (~1.3K users,
  ~$1.2K MRR, ~44% gross margin on consumed credits per
  `UNIT-ECONOMICS.md`), not the prototype's aspirational figures.
- **Replace SSH, not Stripe.** The panel replaces what we do today by
  SSH + SQL (block a user, comp a plan, retry a job, change spend caps).
  Stripe's dashboard stays the money source of truth; we deep-link out.
- **Same auth as today:** `ADMIN_EMAILS` allow-list, 404 to everyone
  else, admin-only nav. Every mutating action is logged.

## 2. Navigation (grouped sidebar)

| Group | Tabs |
|---|---|
| OVERVIEW | Dashboard |
| GROWTH | Users |
| CONTENT | All Videos |
| AI ENGINE | Generation Jobs · AI Costs & Quality |
| MONETIZATION | Revenue · Credits |
| SOCIAL | Publishing |
| SYSTEM | Catalog (existing page) · Audit Log |

Global top bar: search (users / videos / jobs), "updated Xs ago" pill,
admin avatar.

## 3. Pages

### 3.1 Dashboard (Overview)

Real-time operating picture with a time-range switch (Today / 7d / 30d):

- **Alert strip** (the point of the page): provider balance low,
  failure-rate spike, cap tripped, worker down — each with a "View →"
  link into the owning tab.
- **KPI grid** (each card links to its tab): total / new / active
  users, videos generated & published, credits consumed, revenue, MRR,
  paying users, AI cost, gross margin, provider balance.
- **Activation funnel:** signups → first video → 2+ videos → published
  → paid (events table).
- **AI economics mini-card:** margin, cost/video, spend today by stage.
- **Top sports · tone → publish-rate · top takes** (content signals).

### 3.2 Users (GROWTH)

- Search + filter chips (plan, active/churned/blocked, high usage),
  CSV export.
- Table: user, plan, signup, last active, videos, credits, revenue,
  status.
- **Retention cohorts** card: weekly cohorts × D1/D7/D14/D30 from the
  `events` table (small volume is fine — it's one query, not a BI
  suite).
- Per-user drawer: balance, spend, clips with costs, Stripe link, and
  actions — **grant credits**, **mark comped**, **block/unblock**,
  **delete** (typed-email confirmation; replaces `delete-user.py`).

### 3.3 All Videos (CONTENT)

- Grid/List toggle; filter chips: sport, Failed, **Reported**,
  Published. Failed & reported sort first — this is the quality-triage
  surface (a dedicated moderation queue stays deferred; the Reported
  filter covers MVP volume).
- Card: thumbnail, status badge (published / failed w/ reason /
  reported / generating), take, sport · tone · duration · resolution ·
  user, cost + credits charged.
- Per-clip detail: play video, full provenance (per-scene costs,
  prompts, review verdicts, warnings), publish history; actions retry /
  delete (removes files).

### 3.4 Generation Jobs (AI ENGINE)

- KPI strip: live jobs, queued, success rate (24h), avg generation
  time, failed (24h), spend today. Worker heartbeat shown in the page
  header; **Pause queue** button top-right.
- Live queue table: job, take/user, pipeline status (queued →
  generating → quality check → complete / failed), elapsed, cost so
  far; retry / cancel.
- **Spend controls panel:** `MAX_DAILY_SPEND_USD` and
  `MAX_JOB_COST_USD` become DB-backed runtime settings with an audit
  trail (no more SSH-editing `.env`), plus the **kill switch** ("pause
  all generation" = daily cap → $0, the incident mechanism).

### 3.5 AI Costs & Quality (AI ENGINE)

The unit-economics page — "the number that decides the business":

- KPI strip: total spend, cost/video, cost/active user,
  failed-generation cost, **provider balance** (OpenRouter credits API).
- Spend trend (daily) and breakdown by stage: video scenes, reference
  images, script LLM, voice, storage.
- **Quality section** (powered by the existing review pipeline):
  generation success rate, avg review score, character & wardrobe
  consistency, regeneration rate; top failure reasons ranked from
  review verdicts. This is where failure spikes get diagnosed.

### 3.6 Revenue (MONETIZATION)

- KPI strip: total revenue, MRR, top-ups, gross profit after AI cost,
  paying users, churn.
- Weekly revenue trend; MRR by plan (Free / Creator) with movement
  counts (new subs, cancels, conversion, top-up buyers).
- **Transactions table** (read-only): subscriptions, top-ups, refunds —
  every row deep-links into Stripe.

### 3.7 Credits (MONETIZATION)

- KPI strip: issued, consumed (+% of issued), purchased, expired,
  top-up revenue, AI cost per credit.
- **Ledger table:** user, type (consumed / purchased / granted /
  expired), amount, running balance, reason, time.
- Actions: **grant credits** (reason required — feeds audit),
  adjust balance.
- Credits-by-plan card + read-only video price list (prices are code
  constants for MVP; editable pricing table is phase 2, per
  `PRICING.md`).

### 3.8 Publishing (SOCIAL)

- KPI strip: posts today, success rate, failed, scheduled, connected
  accounts, avg time-to-live.
- **By platform:** Instagram (live) with posts/success/API status;
  TikTok / YouTube / X shown as "coming soon" rows so the page grows
  with the roadmap instead of being rebuilt.
- **OAuth health:** token freshness, expiring-token count, error rate —
  expired tokens surface in the queue as "Failed — OAuth expired" with
  a re-auth link.
- Publish queue: video, account, status (publishing / scheduled /
  failed w/ reason / published + permalink), retry.

### 3.9 Audit Log (SYSTEM)

Read view of the `admin_actions` table: when/who, action, target,
reason, filters by admin and action type. Append-only; every mutating
action on any page writes here.

### Catalog (SYSTEM)

The existing character catalog page slots in unchanged as a sidebar
item. Additions when the context pipeline ships: per-character
"storyline notes" freshness and the venue/branding pack (see
VIDEO-REALISM-PLAN).

## 4. Deliberately deferred (from the client prototype)

| Prototype section | Why deferred |
|---|---|
| Analytics suite (funnels/cohorts beyond the Users tab & dashboard funnel) | needs event volume; BI tool later |
| Acquisition / Referrals | no channels tracking or referral system exists |
| Remix Library, Viral Presets, Prompt Library, Repurpose | features that don't exist yet (BRD §8); Prompt Library joins CONTENT when curated take-templates ship |
| AI Models / Model Routing | single video model today; add with multi-model routing (roadmap Oct) |
| Autonomous Agents | not a thing in this product yet |
| Content Moderation queue | "Reported" filter in All Videos covers MVP volume |
| Feedback inbox | user count too small; email works |
| Feature Flags / Experiments | premature at this user count |
| Organizations / Enterprise Accounts | no teams feature |
| Notifications center | alert strip covers it |
| Admin Users management UI | `ADMIN_EMAILS` env list is fine at 2 admins |
| Settings page | caps live in Jobs; the rest stays in env/code for MVP |

Nothing here is rejected forever — each unlocks when its feature ships.

## 5. Cross-cutting requirements

1. **Audit log (MVP-in):** one `admin_actions` table — who, action,
   target, reason, timestamp. Every mutating admin action writes to it;
   §3.9 is just its read view.
2. **Mobile-usable:** same responsive treatment as the catalog page
   (tiles + full-page dialogs). Incidents happen on phones.
3. **No dangerous defaults:** delete/block/cap/kill-switch actions
   require typed confirmation; grants require a reason string.
4. **Read fast, mutate rarely:** lists paginate at 50; dashboards cache
   for 60s; the jobs page may poll faster since it is the live view.
5. **Honest numbers:** margins shown on consumed credits, failed-gen
   cost surfaced, publish rate against generated — no vanity framing.

## 6. Build order

1. Dashboard (alert strip + KPI grid — it's the incident pager)
2. Users (+ retention card; block/grant/delete replace today's scripts)
3. Generation Jobs + runtime spend controls (kills the .env workflow)
4. All Videos (quality triage)
5. AI Costs & Quality (balance + failure diagnosis)
6. Credits + Revenue (after the credit ledger ships)
7. Publishing health view
8. Audit log read view

Catalog is already live; it slots into the sidebar whenever the shell
exists.
