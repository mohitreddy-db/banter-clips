-- BanterClips Phase 1 MVP — canonical DDL (Postgres 16 / Supabase).
-- Mirrors app/models.py; see DATABASE.md for the ERD and rationale.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email                 text NOT NULL UNIQUE,          -- stored lowercased
    supabase_uid          text UNIQUE,                   -- Supabase auth.users.id
    display_name          text,
    plan                  text NOT NULL DEFAULT 'free'
                          CHECK (plan IN ('free', 'creator')),
    plan_renews_at        timestamptz,
    cancel_at_period_end  boolean NOT NULL DEFAULT false,
    stripe_customer_id    text UNIQUE,
    stripe_subscription_id text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    last_login_at         timestamptz
);

CREATE TABLE user_preferences (
    user_id               uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    sports                text[] NOT NULL DEFAULT '{}',
    teams                 text[] NOT NULL DEFAULT '{}',
    players               text[] NOT NULL DEFAULT '{}',
    role                  text,
    onboarding_completed  boolean NOT NULL DEFAULT false,
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE login_tokens (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  text NOT NULL UNIQUE,                    -- sha256 of the raw token
    expires_at  timestamptz NOT NULL,
    used_at     timestamptz
);

CREATE TABLE clips (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    take              text NOT NULL CHECK (char_length(take) BETWEEN 10 AND 280),
    sport             text NOT NULL CHECK (sport IN ('NBA', 'NFL', 'Soccer', 'MLB')),
    tone              text NOT NULL CHECK (tone IN ('Funny', 'Savage', 'Hype', 'Bold')),
    status            text NOT NULL DEFAULT 'queued' CHECK (status IN (
                          'queued', 'planning_story', 'creating_voice',
                          'designing_characters', 'generating_scenes',
                          'animating_scenes', 'assembling_video', 'validating',
                          'ready', 'failed')),
    stage_index       integer NOT NULL DEFAULT 0,
    duration_target   integer NOT NULL DEFAULT 15,      -- 10/15/30; >15 Creator-only
    error             text,
    duration_seconds  numeric(4, 1),
    video_url         text,
    thumb_gradient    text,
    watermarked       boolean NOT NULL DEFAULT true,     -- frozen at completion
    created_at        timestamptz NOT NULL DEFAULT now(),
    completed_at      timestamptz,
    current_step      text,                              -- live step, in the user's words
    video_key         text,                              -- storage key: users/{uid}/clips/{cid}/final.mp4
    poster_key        text,
    cost_usd          numeric(7,3),                      -- what generation cost us
    provenance        jsonb,                             -- brief, plan, review verdicts, model versions
    is_simulated      boolean NOT NULL DEFAULT false     -- demo run: never publishable
);
CREATE INDEX clips_owner_month ON clips (user_id, status, completed_at);

-- Durable work queue. Generation used to run on a thread inside the API, so a
-- deploy mid-render lost the work silently. A row survives both a deploy and a
-- crash; a separate worker process claims jobs with FOR UPDATE SKIP LOCKED.
CREATE TABLE jobs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind              text NOT NULL,                     -- 'generate_clip'
    clip_id           uuid REFERENCES clips(id) ON DELETE CASCADE,
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'done', 'failed')),
    attempts          integer NOT NULL DEFAULT 0,
    max_attempts      integer NOT NULL DEFAULT 2,
    run_after         timestamptz NOT NULL DEFAULT now(), -- retry backoff
    locked_by         text,                               -- host:pid of the worker
    locked_at         timestamptz,                        -- heartbeat; stale => reclaim
    error             text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    finished_at       timestamptz
);
CREATE INDEX jobs_claimable ON jobs (status, run_after);

CREATE TABLE social_accounts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform      text NOT NULL CHECK (platform IN
                      ('instagram', 'tiktok', 'youtube', 'x', 'linkedin')),
    handle        text NOT NULL,
    status        text NOT NULL DEFAULT 'connected'
                  CHECK (status IN ('connected', 'revoked')),
    access_token  text,                                  -- long-lived IG token (or mock)
    platform_user_id text,                               -- IG professional account id
    token_expires_at timestamptz,                        -- auto-refreshed near expiry
    connected_at  timestamptz NOT NULL DEFAULT now(),
    revoked_at    timestamptz,
    UNIQUE (user_id, platform)
);

CREATE TABLE publishes (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clip_id            uuid NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
    social_account_id  uuid NOT NULL REFERENCES social_accounts(id) ON DELETE CASCADE,
    caption            text NOT NULL DEFAULT '',
    status             text NOT NULL DEFAULT 'queued'
                       CHECK (status IN ('queued', 'uploading', 'published', 'failed')),
    error              text,
    external_url       text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    published_at       timestamptz
);
CREATE INDEX publishes_clip ON publishes (clip_id, created_at DESC);

-- Audit/idempotency log for Stripe webhook deliveries. Stripe is the billing
-- ledger; we only mirror derived entitlement (users.plan) + this trail.
CREATE TABLE stripe_events (
    id                text PRIMARY KEY,            -- evt_...
    type              text NOT NULL,
    event_created_at  timestamptz,
    processed_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
    name        text NOT NULL,
    props       jsonb NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_name_time ON events (name, created_at);
