# BanterClips

Turn any sports opinion into a cinematic, post-ready vertical video — then
publish it to social without leaving the app.

**Phase 1 MVP:** sports opinion → generated 12–15s vertical video → preview →
publish (all plans, watermarked on Free) or download (Creator only).

## Repository layout

```
banter-clips/
├── frontend/              React SPA — deployed to Vercel
├── backend/               FastAPI API — deployed to a DigitalOcean droplet
├── infra/                 ⚠ gitignored — droplet IPs, certs, keys, Supabase creds
├── BRD.md                 Business requirements (v1.4) — the source of truth
├── VIDEO-PIPELINE-SPEC.md Companion technical spec for the real video pipeline
├── PRD.md / PRD2.md       Earlier product docs (historical)
├── figma-scripts/         Scripter scripts that build/update the Figma designs
├── artifacts/             Experiment outputs (media files gitignored)
└── script.txt             Prompt pack for testing video-gen providers
```

`frontend/` and `backend/` are fully independent projects: separate
dependencies (`package-lock.json` vs `requirements.txt`), separate `.env`
files, separate deploys. This repo just keeps them under one roof with the
shared product docs.

## Stack at a glance

| Piece | Tech | Deploy target |
|---|---|---|
| Frontend | React 18 · Vite 6 · Tailwind 4 · react-router-dom 7 | Vercel |
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · PyJWT | DigitalOcean droplet |
| Database | Postgres 16 (local docker) → Supabase in production | Supabase |
| Video generation | **Dummy mode** — honest job stages + pre-rendered demo MP4, pending the provider bake-off (see VIDEO-PIPELINE-SPEC.md) | — |

## Run it locally

```bash
# 1. Database (postgres 16 in docker, port 5433)
docker start banterclips-postgres   # created with user banter / db banterclips

# 2. Backend  →  http://localhost:8000  (docs at /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                # defaults work for local dev
.venv/bin/uvicorn app.main:app --reload --port 8000

# 3. Frontend  →  http://localhost:5173
cd frontend
npm install
npm run dev
```

Sign in with any email — in `DEV_MODE` the magic link resolves instantly
without a mailbox. Type `[fail]` inside a take or caption to demo the
failure + free-retry paths.

## Deployment

- **Frontend → Vercel:** import the repo, set the project root to `frontend/`,
  add `VITE_API_URL=https://<backend-domain>`. `vercel.json` already handles
  the SPA rewrite.
- **Backend → droplet:** install Python 3.12, clone, create the venv, run
  uvicorn behind nginx/caddy with TLS. Set `DATABASE_URL` (Supabase),
  `JWT_SECRET`, `CORS_ORIGINS=https://<vercel-domain>`, `DEV_MODE=false`,
  `API_BASE_URL=https://<backend-domain>`.
- **Database → Supabase:** apply `backend/schema.sql`; details and keys live
  in `infra/supabase.md` (never committed).

All deployment secrets, IPs, certs and key files belong in `infra/` — that
folder is gitignored by design.

## Where things are documented

- Product scope and rules: `BRD.md`
- Database entities/ERD: `backend/DATABASE.md` (+ `backend/schema.sql`)
- API and backend details: `backend/README.md`
- Frontend structure and UX flows: `frontend/README.md`
- Real video pipeline design (future): `VIDEO-PIPELINE-SPEC.md`
