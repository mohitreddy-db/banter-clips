# BanterClips — Database Schema (Phase 1 MVP)

Postgres 16. Local dev runs in the `banterclips-postgres` container
(`postgresql://banter:banter_dev@localhost:5433/banterclips`); production is
Supabase (same DDL — no extensions beyond `pgcrypto` for `gen_random_uuid()`,
which Supabase ships by default).

The SQLAlchemy models in `app/models.py` are the source of truth at runtime
(`Base.metadata.create_all` on startup for the MVP). `schema.sql` mirrors them
as plain DDL for review and for applying to Supabase later.

## Entity–relationship diagram

```mermaid
erDiagram
    users ||--o| user_preferences : "has"
    users ||--o{ login_tokens : "signs in with"
    users ||--o{ clips : "creates"
    users ||--o{ social_accounts : "connects"
    users ||--o{ events : "emits"
    clips ||--o{ publishes : "is published as"
    social_accounts ||--o{ publishes : "receives"

    users {
        uuid id PK
        text email UK "stored lowercased"
        text supabase_uid UK "Supabase Auth identity"
        text display_name
        text plan "free | creator — derived from Stripe"
        timestamptz plan_renews_at
        boolean cancel_at_period_end
        text stripe_customer_id UK
        text stripe_subscription_id
        timestamptz created_at
        timestamptz last_login_at
    }
    stripe_events {
        text id PK "evt_... webhook delivery"
        text type
        timestamptz event_created_at
        timestamptz processed_at
    }
    user_preferences {
        uuid user_id PK,FK
        text_array sports
        text_array teams
        text_array players
        text role "Sports Fan | Creator | Podcaster | Media Company | Fantasy Creator"
        boolean onboarding_completed
        timestamptz updated_at
    }
    login_tokens {
        uuid id PK
        uuid user_id FK
        text token_hash UK
        timestamptz expires_at
        timestamptz used_at
    }
    clips {
        uuid id PK
        uuid user_id FK
        text take "10-280 chars"
        text sport "NBA | NFL | Soccer | MLB"
        text tone "Funny | Savage | Hype | Bold"
        text status "queued .. ready | failed"
        int stage_index "0-6 while generating"
        int duration_target "10/15/30s; >15 Creator-only"
        text error
        numeric duration_seconds
        text video_url
        text thumb_gradient "CSS gradient for card art"
        boolean watermarked "plan at completion time"
        timestamptz created_at
        timestamptz completed_at
    }
    social_accounts {
        uuid id PK
        uuid user_id FK
        text platform "instagram | tiktok | youtube | x | linkedin"
        text handle
        text status "connected | revoked"
        text access_token "OAuth token (mock in MVP)"
        timestamptz connected_at
        timestamptz revoked_at
    }
    publishes {
        uuid id PK
        uuid clip_id FK
        uuid social_account_id FK
        text caption
        text status "queued | uploading | published | failed"
        text error
        text external_url "link to live post"
        timestamptz created_at
        timestamptz published_at
    }
    events {
        bigint id PK
        uuid user_id FK "nullable — anonymous landing events"
        text name "BR-11 event names"
        jsonb props
        timestamptz created_at
    }
```

## Entities and the business rules they encode

### `users`
One row per account. `plan` is the whole monetization switch (BR-15):
`free` → publish-only, watermark always, 5 successful videos/month;
`creator` → downloads + watermark-free, 30/month. `cancel_at_period_end`
models "downgrade applies at period end" without deleting anything.

**Billing design: Stripe is the ledger.** We never mirror invoices/charges —
`plan`, `stripe_customer_id`, `stripe_subscription_id`, `plan_renews_at`, and
`cancel_at_period_end` are *derived entitlement state*, converged from
Stripe's API on every billing webhook (webhooks are treated as triggers, not
truth, because Stripe delivers at-least-once and unordered). The sync also
enforces one-live-subscription-per-user by cancelling extras.

### `stripe_events`
Audit log + idempotency marker: one row per processed Stripe webhook
delivery. Duplicate deliveries are acknowledged without side effects; the
trail answers "what did billing do and when" during disputes/debugging.

### `user_preferences` (1:1 with users)
The entire output of onboarding (BR-14): sports multi-select, favorite
teams/players tags, role. Only pre-fills the Studio — no feed. Every field
nullable/empty because every onboarding step is skippable.
`onboarding_completed` drives the "show onboarding once" redirect.

### `login_tokens`
Magic-link sign-in (BR-02, "preferably email magic link"). We store only a
SHA-256 hash of the token; 15-minute expiry; single use (`used_at`).
In `DEV_MODE` the API returns the raw token in the response instead of
emailing it — same table, same verification path.

### `clips`
One row per generation job — the job *is* the clip. `status` walks the honest
BR-07 stages: `queued → planning_story → creating_voice → designing_characters
→ generating_scenes → animating_scenes → assembling_video → validating →
ready | failed`. Monthly allowance counts **only `status='ready'` rows**
(`completed_at` in the current calendar month) — failed jobs and retries never
count (BR-09). `watermarked` is frozen at completion from the owner's plan so
an upgrade doesn't silently rewrite history; new clips after upgrade are clean.

### `social_accounts`
BR-13 OAuth connections. One row per (user, platform); `revoked` rows are kept
for audit and reconnect. `access_token` is a mock value until the real
platform OAuth app is approved — the column (and revocation path) is already
shaped for the real token.

### `publishes`
An explicit per-clip publish action (never automatic). Honest status
`queued → uploading → published | failed`; `external_url` is the link to the
live post; a failed publish is retried by inserting a new attempt — history
stays. Publishing never touches the generation allowance.

### `events`
BR-11 minimum product analytics: `generation_started`, `publish_succeeded`,
`upgrade_completed`, … written server-side where possible, plus a
`POST /events` for client-only moments (CTA clicks, preview plays). No
dashboard — query with SQL when evaluating the gates.

## Derived values (queries, not columns)

| Value | Query |
|---|---|
| Videos used this month | `SELECT count(*) FROM clips WHERE user_id=$1 AND status='ready' AND completed_at >= date_trunc('month', now())` |
| Monthly limit | `5` if plan=`free` else `30` (config, not DB) |
| Can download | `plan = 'creator'` |

## Migration path to Supabase

1. Create the Supabase project, note the pooler `DATABASE_URL` in `infra/supabase.md`.
2. Run `schema.sql` in the Supabase SQL editor (or point the backend's
   `DATABASE_URL` at Supabase and let `create_all` do it once).
3. Backend on the droplet gets `DATABASE_URL` switched — no code change.
