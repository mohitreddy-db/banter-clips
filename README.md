# BanterClips

Turn any sports opinion into a cinematic, post-ready vertical video — then
publish it to social without leaving the app.

**Live:** https://www.banterclips.com · API: https://api.banterclips.com

## Documentation map — where the truth lives

| Topic | Source of truth |
|---|---|
| Product scope, business rules, plans | [`BRD.md`](BRD.md) (v1.4) |
| Database schema / ERD | [`backend/DATABASE.md`](backend/DATABASE.md) + [`backend/schema.sql`](backend/schema.sql) |
| Backend — stack, local setup, API, env | [`backend/README.md`](backend/README.md) |
| Frontend — stack, local setup, env | [`frontend/README.md`](frontend/README.md) |
| Deploying from scratch (runbook) | [`deploy/README.md`](deploy/README.md) |
| Search presence — crawling, metadata, structured data | [`SEO.md`](SEO.md) |
| **Production state & secrets** (droplet, keys, Supabase, Vercel, DNS, Meta) | `infra/PROD.md` — **gitignored**, lives only on this machine |

## Repository layout

```
banter-clips/
├── frontend/    React SPA — Vercel          (own package.json + .env)
├── backend/     FastAPI API — DO droplet    (own requirements.txt + .env)
├── deploy/      Droplet setup script, systemd unit, Caddyfile, runbook
├── infra/       ⚠ gitignored — prod details, creds, DNS, key inventory
└── BRD.md       Business requirements — the product source of truth
```

`frontend/` and `backend/` are independent projects: separate dependencies,
separate `.env` files (each has a commented `.env.example`), separate deploys.

## Architecture

| Piece | Local dev | Production |
|---|---|---|
| Frontend | Vite dev server :5173 | Vercel — www.banterclips.com (auto-deploys `main`) |
| Backend | uvicorn :8000 | Droplet 168.144.149.99 — api.banterclips.com (Caddy TLS) |
| App database | Postgres 16 in docker (`banterclips-postgres`, :5433) | Supabase Postgres |
| Auth | Supabase Auth (same project) or offline dev magic-link | Supabase Auth |
| Instagram | Mock connect, or real OAuth via cloudflared tunnel | Real OAuth + Reels publishing |
| Video generation | **Dummy** — honest job stages + pre-rendered demo MP4 | Same (provider bake-off pending) |

## Local quick start

```bash
# 0. one-time: local postgres (skip if the container exists — then just `docker start banterclips-postgres`)
docker run -d --name banterclips-postgres \
  -e POSTGRES_USER=banter -e POSTGRES_PASSWORD=banter_dev -e POSTGRES_DB=banterclips \
  -p 5433:5432 -v banterclips_pgdata:/var/lib/postgresql/data \
  --restart unless-stopped postgres:16-alpine

# 1. backend  → http://localhost:8000 (docs at /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # local defaults work as-is
.venv/bin/uvicorn app.main:app --reload --port 8000

# 2. frontend → http://localhost:5173
cd frontend
npm install
cp .env.example .env          # then choose local vs prod API (see the file)
npm run dev
```

Full details, env-variable tables, and demo tricks: the two app READMEs.

## Deploying changes

- **Frontend:** `git push` → Vercel auto-deploys `main`.
- **Backend:** `git push`, then the one-liner in `infra/PROD.md` (git pull +
  service restart on the droplet).
