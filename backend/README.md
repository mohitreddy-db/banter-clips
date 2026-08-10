# BanterClips API (backend)

FastAPI backend for the Phase 1 MVP ([`../BRD.md`](../BRD.md)): Supabase-backed
auth, clip generation jobs (dummy pipeline until the provider bake-off), plan-
gated delivery, real Instagram connect + Reels publishing, and BR-11 analytics.

**Prod:** https://api.banterclips.com (droplet — see `infra/PROD.md`) ·
**Interactive docs:** `/docs` on any running instance.

## Tech stack

| Layer | Choice |
|---|---|
| Language / framework | Python 3.12 · FastAPI 0.115 · uvicorn |
| ORM / DB | SQLAlchemy 2 + psycopg 3 → Postgres 16 (local docker) / Supabase (prod) |
| Auth | Supabase Auth (email+password, magic links) exchanged for our own PyJWT 30-day sessions |
| Social publishing | Instagram Graph API (Business Login OAuth, Reels container publish) |
| Video generation | **Dummy worker** — walks the honest BR-07 stages, attaches a demo MP4. Real pipeline design: `../VIDEO-PIPELINE-SPEC.md` (local-only doc); legacy experiments in `app/pipeline/` |

## Local setup (from zero)

```bash
# 1. Database — Postgres 16 in docker (one-time; later just `docker start banterclips-postgres`)
docker run -d --name banterclips-postgres \
  -e POSTGRES_USER=banter -e POSTGRES_PASSWORD=banter_dev -e POSTGRES_DB=banterclips \
  -p 5433:5432 -v banterclips_pgdata:/var/lib/postgresql/data \
  --restart unless-stopped postgres:16-alpine

# 2. Python env
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Config — local defaults work as-is; see comments in the file
cp .env.example .env

# 4. A demo video for the dummy generator
mkdir -p data/media && cp <any-vertical>.mp4 data/media/demo.mp4

# 5. Run — tables are created automatically on first startup
.venv/bin/uvicorn app.main:app --reload --port 8000
curl localhost:8000/health        # → {"ok": true, ...}
```

Inspect local data anytime:
`docker exec -it banterclips-postgres psql -U banter -d banterclips`
(connection string: `postgresql://banter:banter_dev@localhost:5433/banterclips`)

### Dev conveniences

- `DEV_MODE=true` → `POST /auth/request-link` returns the magic-link token in
  the response — sign in with any email, no mailbox, no Supabase needed.
- A take containing `[fail]` fails generation at the scene stage; a caption
  containing `[fail]` fails a (mock) publish — demos the free-retry paths.
- Real Instagram from localhost needs an https tunnel; see `.env.example`.

## Environment — local vs prod

| Variable | Local | Prod (droplet) |
|---|---|---|
| `DATABASE_URL` | docker postgres `:5433` | Supabase Postgres |
| `JWT_SECRET` | anything | long random, rotated = global sign-out |
| `CORS_ORIGINS` | localhost ports | `banterclips.com` domains (+ localhost for dev-against-prod) |
| `DEV_MODE` | `true` | **`false`** (disables the instant magic-link) |
| `API_BASE_URL` | `http://localhost:8000` | `https://api.banterclips.com` — Instagram fetches videos from here |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` | same as prod | same |
| `META_APP_ID/SECRET`, `IG_REDIRECT_URI` | empty (mock) or tunnel | real app + prod callback |
| `FRONTEND_URL` | `http://localhost:5173` | `https://www.banterclips.com` |

Full commented reference: [`.env.example`](.env.example). Real prod values:
`/opt/banter-clips/backend/.env` on the droplet + `infra/` locally.

## Project layout

```
app/
├── main.py            App wiring: CORS, routers, /media static, /health, create_all
├── config.py          Settings from .env (pydantic-settings)
├── db.py              Engine + session factory
├── models.py          SQLAlchemy models — runtime source of truth for the schema
├── schemas.py         Pydantic request/response shapes
├── security.py        Login tokens + session JWTs
├── deps.py            get_current_user, allowance math, event recorder
├── routers/
│   ├── auth.py        POST /auth/supabase (token exchange) · dev magic-link
│   ├── me.py          GET /me · GET /me/usage · PATCH /me/preferences
│   ├── clips.py       CRUD · /retry · /download (Creator) · /publish · publish status
│   ├── socials.py     Instagram OAuth (authorize-url/callback) · token auto-refresh · mock connect
│   ├── billing.py     /billing/upgrade · /billing/cancel (mock Stripe, webhook-shaped)
│   └── events.py      POST /events — client-side analytics (BR-11)
├── services/
│   ├── generation.py  Dummy generation worker (stage machine → ready/failed)
│   └── publishing.py  Publish worker — real Reels path + mock path
└── pipeline/          Legacy real-generation experiments (deps: requirements-pipeline.txt)
```

Schema documentation: [`DATABASE.md`](DATABASE.md) (ERD + rationale) and
[`schema.sql`](schema.sql) (canonical DDL, applied to Supabase as migration
`initial_banterclips_schema`).

## Business rules encoded here (BRD anchors)

- **Plans (BR-15):** `free` = 5 successful videos/mo, publish-only, watermark
  always → download returns `403 upgrade_required`. `creator` = 30/mo, HD
  download, watermark-free.
- **Allowance (BR-09):** only clips that reached `ready` this calendar month
  count; failures and retries are free; at the cap `POST /clips` returns
  `402 limit_reached`.
- **Honest status (BR-07):** workers write each stage as it actually starts;
  clients poll `GET /clips/{id}`.
- **Publishing (BR-13):** explicit per-clip action; honest
  queued/uploading/published/failed; permalink stored; Instagram long-lived
  tokens auto-refresh inside their last 15 days (`maybe_refresh_token`).
- **Ownership (BR-02/BR-12):** every query is scoped to the session user.

## Auth model

```
browser ── email+password / magic link ──▶ Supabase Auth
browser ── supabase access token ────────▶ POST /auth/supabase
backend ── verifies token with Supabase, find-or-create local user
        └─ issues OUR 30-day JWT → used on every other endpoint
```

Sessions are stateless JWTs (nothing stored server-side); `users.supabase_uid`
links the two systems.

## Deployment

Runbook: [`../deploy/README.md`](../deploy/README.md). Live prod details,
keys, and the update one-liner: `infra/PROD.md` (gitignored).
