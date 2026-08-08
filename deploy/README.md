# Deploying BanterClips to production

Architecture: **Vercel** (frontend) → **DigitalOcean droplet** (FastAPI behind
Caddy with auto-TLS) → **Supabase** (Postgres + Auth). Schema is already
applied to the Supabase project (`taphbakizdagamimbhjh`, migration
`initial_banterclips_schema`).

## 1. Droplet (backend)

Create an Ubuntu 24.04 droplet (the $6/mo basic is plenty for beta), add your
SSH key, note the IP in `infra/droplet.md`. Point a DNS A-record at it, e.g.
`api.<your-domain>` — Caddy will fetch the TLS cert automatically.

```bash
ssh root@<droplet-ip>
# the droplet needs read access to the GitHub repo:
#   easiest: create a fine-grained deploy key:  ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519
#   add the .pub as a read-only Deploy Key in GitHub repo settings
git clone git@github.com:mohitreddy-db/banter-clips.git /opt/banter-clips
bash /opt/banter-clips/deploy/setup-droplet.sh
```

Then fill `/opt/banter-clips/backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://postgres:<DB-PASSWORD>@db.taphbakizdagamimbhjh.supabase.co:5432/postgres
JWT_SECRET=<long random string — openssl rand -hex 32>
CORS_ORIGINS=https://<your-vercel-domain>
DEV_MODE=false
STAGE_SECONDS=1.4
API_BASE_URL=https://api.<your-domain>
SUPABASE_URL=https://taphbakizdagamimbhjh.supabase.co
SUPABASE_ANON_KEY=<anon key — infra/supabase.md>
META_APP_ID=<infra/meta.md>
META_APP_SECRET=<infra/meta.md>
IG_REDIRECT_URI=https://api.<your-domain>/socials/instagram/callback
FRONTEND_URL=https://<your-vercel-domain>
```

Edit `/etc/caddy/Caddyfile` (replace `api.example.com`), copy a demo video:

```bash
scp backend/data/media/demo.mp4 root@<droplet-ip>:/opt/banter-clips/backend/data/media/
systemctl restart banterclips-api caddy
curl https://api.<your-domain>/health   # → {"ok":true,...}
```

**Updates after a git push:**
```bash
ssh root@<droplet-ip> 'cd /opt/banter-clips && git pull && backend/.venv/bin/pip install -q -r backend/requirements.txt && systemctl restart banterclips-api'
```

## 2. Vercel (frontend)

1. vercel.com → Add New Project → import `mohitreddy-db/banter-clips`.
2. **Root Directory: `frontend`** (build command/output auto-detected from Vite).
3. Environment variables (Production):
   - `VITE_API_URL=https://api.<your-domain>`
   - `VITE_SUPABASE_URL=https://taphbakizdagamimbhjh.supabase.co`
   - `VITE_SUPABASE_ANON_KEY=<anon key>`
4. Deploy. Every push to `main` now auto-deploys.

## 3. Supabase dashboard (one-time)

- Auth → URL Configuration → **Site URL** = `https://<your-vercel-domain>`;
  add `http://localhost:5173` to Additional Redirect URLs for local dev.
- Settings → Database → note/reset the **database password** (needed for the
  droplet's `DATABASE_URL`). Store it in `infra/supabase.md`.
- Before public launch: Auth → custom SMTP (built-in mailer is rate-limited).

## 4. Meta dashboard (one-time)

Instagram → API setup with Instagram login → Business login settings →
OAuth redirect URIs → **add** `https://api.<your-domain>/socials/instagram/callback`
(keep the tunnel one for local dev, or remove it later).

## 5. Post-deploy smoke test

1. Open the Vercel URL → sign up with a real email → confirm → sign in.
2. Onboard → connect Instagram (real consent) → generate → publish → check
   the Reel + permalink.
3. `https://api.<your-domain>/docs` loads; `/health` returns ok.

## Costs

| Item | $ |
|---|---|
| Vercel hobby | $0 |
| Droplet basic | $6/mo |
| Supabase project | $10/mo (already active) |
| Domain | whatever you pay now |
