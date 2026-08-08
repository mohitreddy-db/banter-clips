# BanterClips API (backend)

FastAPI backend for the Phase 1 MVP: magic-link auth, clip generation jobs
(dummy pipeline for now), plan-gated delivery, social connect + publish, and
minimum product analytics.

## Tech stack

- **Python 3.12 · FastAPI 0.115** — API framework, OpenAPI docs at `/docs`
- **SQLAlchemy 2 + psycopg 3** — Postgres ORM (Postgres 16 locally, Supabase in prod)
- **PyJWT** — 30-day session tokens; magic-link sign-in (no passwords)
- **uvicorn** — ASGI server
- Video generation: **dummy mode** (`app/services/generation.py`) — walks the
  honest BR-07 stages on a background thread and attaches a pre-rendered demo
  MP4. The real pipeline (see `../VIDEO-PIPELINE-SPEC.md` and `app/pipeline/`)
  slots in behind the same job model once the provider bake-off is done.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # local defaults work as-is
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Requires the `banterclips-postgres` container (Postgres 16, port 5433):

```bash
docker run -d --name banterclips-postgres \
  -e POSTGRES_USER=banter -e POSTGRES_PASSWORD=banter_dev -e POSTGRES_DB=banterclips \
  -p 5433:5432 -v banterclips_pgdata:/var/lib/postgresql/data \
  --restart unless-stopped postgres:16-alpine
```

Tables are created automatically on startup (`create_all`). The canonical DDL
for review / Supabase is `schema.sql`; the ERD and rationale are in
`DATABASE.md`.

## Project layout

```
app/
├── main.py            FastAPI app, CORS, routers, /media static, /health
├── config.py          Settings from .env (pydantic-settings)
├── db.py              Engine + session
├── models.py          SQLAlchemy models (source of truth for the schema)
├── schemas.py         Pydantic request/response models
├── security.py        Magic-link tokens + session JWTs
├── deps.py            get_current_user, usage/allowance math, event recorder
├── routers/
│   ├── auth.py        POST /auth/request-link · /auth/verify
│   ├── me.py          GET /me · GET /me/usage · PATCH /me/preferences
│   ├── clips.py       CRUD + /retry + /download + /publish + publish status
│   ├── socials.py     GET /socials · POST /socials/connect · DELETE /socials/{platform}
│   ├── billing.py     POST /billing/upgrade · /billing/cancel (mock Stripe)
│   └── events.py      POST /events — client-side BR-11 analytics
├── services/
│   ├── generation.py  Dummy generation worker (BR-07 stages → ready/failed)
│   └── publishing.py  Dummy publish worker (queued → uploading → published)
└── pipeline/          Legacy real-generation experiments (OpenAI script/TTS/
                       captions/render) — kept for the post-bake-off build;
                       extra deps in requirements-pipeline.txt
```

## Business rules encoded here

- **Free vs Creator (BR-15):** `free` = 5 successful videos/mo, publish-only,
  watermark always. `creator` = 30/mo, HD download, no watermark. Download on
  Free returns `403 {code: upgrade_required}`.
- **Allowance (BR-09):** only `status='ready'` clips completed this calendar
  month count. Failed jobs and retries are free. At the limit, creating a clip
  returns `402 {code: limit_reached}`.
- **Honest status (BR-07):** clip `status` is written by the worker as each
  stage actually starts; the frontend polls `GET /clips/{id}`.
- **Publishing (BR-13):** explicit per-clip `POST /clips/{id}/publish` with a
  connected account; honest `queued/uploading/published/failed` status with a
  link to the live post; failed publishes retry free.
- **Ownership (BR-02/BR-12):** every clip/social/publish query is scoped to
  the session user; cross-account access 404s.

## Demo affordances (dev only)

- `DEV_MODE=true` → `POST /auth/request-link` returns the magic-link token in
  the response (`dev_token`) so no mailbox is needed.
- A take containing `[fail]` fails generation at the scene stage; a caption
  containing `[fail]` fails the publish — both to demo the retry paths.

## Deploying to the droplet

1. Clone, create the venv, install `requirements.txt`.
2. `.env`: Supabase `DATABASE_URL`, strong `JWT_SECRET`,
   `CORS_ORIGINS=https://<vercel-domain>`, `DEV_MODE=false`,
   `API_BASE_URL=https://<api-domain>`.
3. Run uvicorn (systemd service) behind nginx/caddy with TLS.
4. Apply `schema.sql` to Supabase once (or let the first boot `create_all`).

Secrets (droplet IP, ssh keys, Supabase creds) live in the repo-root
`infra/` folder, which is gitignored.
