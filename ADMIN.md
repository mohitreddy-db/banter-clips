# BanterClips — Admin Panel (MVP scope)

Version 1.0 · 2026-08-21 · Companion to `PRICING.md` (credits) and the
existing `/admin` catalog page. The client's prototype shows a ~30-section
enterprise console; this doc cuts it to what an MVP with one operator
actually needs, and maps every section to data we already have.

## 1. Principles

- **One operator, real data.** Every widget must read from tables that exist
  (users, clips, jobs, events, catalog, Stripe) — no vanity metrics.
- **Replace SSH, not Stripe.** The panel replaces the things we do today by
  SSH + SQL (block a user, comp a plan, retry a job, check spend). Stripe's
  own dashboard stays the money source of truth; we link out to it.
- **Same auth as today:** `ADMIN_EMAILS` allow-list, 404 to everyone else,
  admin-only nav. Every admin action is logged.

## 2. MVP sections (6)

### 2.1 Dashboard (home)

The operating picture on one screen. All numbers computable today:

| Widget | Source |
|---|---|
| Users: total / new (7d) / active (7d) | `users`, `events` |
| Videos: generated, success rate, publish rate | `clips`, `publishes` |
| AI spend today / 7d, cost per video | `clips.cost_usd` |
| **Provider balance** (OpenRouter credits left) | OpenRouter credits API |
| Spend caps status (daily cap, per-job cap) | settings |
| Revenue: MRR, paying users | Stripe (cached) |
| Credits issued vs consumed (after credits ship) | credit ledger |
| Alert strip: failure-rate spike, balance low, cap tripped, worker down | computed |

The alert strip is the point of the page: today the OpenRouter balance
going negative was invisible until generation broke.

### 2.2 Users

- Search/list: email, plan, credits balance, videos, spend, last login,
  blocked?
- Per-user drawer: their clips (with costs), publishes, Stripe customer
  link, credit history.
- Actions: **block / unblock** (silent blocklist — exists), **grant
  credits / comp plan**, **delete user** (full erasure — the delete-user
  script becomes a button with a typed confirmation).

### 2.3 Videos

- All clips across users: thumbnail, take, user, status, duration,
  resolution, cost, credits charged, created.
- Filters: status (failed first), user, sport, date.
- Per-clip: play the video, full provenance (per-scene costs, review
  verdicts, warnings, prompts), publish history.
- Actions: **retry failed**, **delete** (removes files too). This is the
  quality-triage surface — it's how bad outputs get found and diagnosed.

### 2.4 Generation Jobs (queue + spend control)

- Live queue: queued / running / recently failed jobs, per-job elapsed and
  cost so far, worker heartbeat (is the worker alive?).
- Actions: retry job, cancel job.
- **Spend controls editable here**: daily cap (`MAX_DAILY_SPEND_USD`) and
  per-job cap (`MAX_JOB_COST_USD`) become DB-backed runtime settings with
  an audit trail — no more SSH-editing `.env` to open/close generation.
- Kill switch: "pause all generation" toggle (sets the daily cap to ~0,
  the mechanism we already used in an incident).

### 2.5 Catalog (already live — folded in)

The existing character catalog page becomes a tab of the admin panel:
tile grid, edit dialog, stills history + approval, research auto-fill,
generate-with-notes. Documented here as part of admin, not separately.
Additions when the context pipeline ships: per-character "storyline notes"
freshness and the venue/branding pack (see VIDEO realism plan).

### 2.6 Billing & Credits

- Read view: transactions (subscriptions, top-ups), per-user credit
  ledger entries, refunds — with deep links into Stripe for anything
  money-touching.
- Actions: grant promo credits (logged, with reason), mark account comped.
- Per `PRICING.md`: credit price list shown read-only with a "prices are
  code constants" note for MVP; editable pricing table is phase 2.

## 3. Deliberately deferred (from the client prototype)

| Prototype section | Why deferred |
|---|---|
| Analytics suite (funnels, cohorts, retention curves) | needs event volume we don't have; `events` table + a BI tool later |
| Acquisition / Retention / Referrals | no referral system exists |
| Remix Library, Viral Presets, Prompt Library, Repurpose | features that don't exist yet (BRD §8) |
| AI Models / Model Routing | single video model today; add with multi-model routing (roadmap Oct) |
| Autonomous Agents | not a thing in this product yet |
| Content Moderation queue | MVP: flagged/refused takes appear in Videos with a filter; a dedicated queue needs volume |
| Feature Flags / Experiments | premature at this user count |
| Organizations / Enterprise Accounts | no teams feature |
| Notifications center | journal + alert strip cover it |
| Admin Users management UI | `ADMIN_EMAILS` env list is fine at 2 admins |

Nothing here is rejected forever — each unlocks when its feature ships.

## 4. Cross-cutting requirements

1. **Audit log (lightweight, MVP-in):** one `admin_actions` table — who,
   action, target, reason, timestamp. Every mutating admin action writes
   to it. The prototype's "Audit Logs" page is just a read view of this.
2. **Mobile-usable:** same responsive treatment as the catalog page
   (tiles + full-page dialogs). Incidents happen on phones.
3. **No dangerous defaults:** delete/block/cap actions require typed
   confirmation; grants require a reason string (feeds the audit log).
4. **Read fast, mutate rarely:** lists paginate at 50; dashboards cache
   for 60s; nothing polls faster than the data changes.

## 5. Build order

1. Dashboard (alert strip + spend/balance first — it's the incident pager)
2. Users (block/grant/delete replace today's scripts)
3. Videos (quality triage)
4. Jobs + runtime spend controls (kills the .env-editing workflow)
5. Billing & credits view (after the credit ledger ships)
6. Audit log read view

Catalog is already live; it slots in as a tab whenever the shell exists.
