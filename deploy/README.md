# Deploying BanterClips to production

Architecture: **Vercel** (frontend) → **DigitalOcean droplet** (FastAPI behind
Caddy with auto-TLS) → **Supabase** (Postgres + Auth). Schema is already
applied to the Supabase project (`taphbakizdagamimbhjh`, migration
`initial_banterclips_schema`).

Debugging something? See **[LOGS.md](LOGS.md)** — the logs runbook (which
service logs what, journalctl recipes per symptom, Stripe/Vercel/Supabase log
locations).

## 1. Droplet (backend)

Create an Ubuntu 24.04 droplet (the $6/mo basic is plenty for beta), add your
SSH key, note the IP in `infra/droplet.md`. Point a DNS A-record at it, e.g.
`api.banterclips.com` — Caddy will fetch the TLS cert automatically.

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
# Supabase session pooler (IPv4 — droplets often lack IPv6 for the direct host)
DATABASE_URL=postgresql+psycopg://postgres.taphbakizdagamimbhjh:<DB-PASSWORD>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
JWT_SECRET=<long random string — openssl rand -hex 32>
CORS_ORIGINS=https://www.banterclips.com
DEV_MODE=false
STAGE_SECONDS=1.4
API_BASE_URL=https://api.banterclips.com
SUPABASE_URL=https://taphbakizdagamimbhjh.supabase.co
SUPABASE_ANON_KEY=<anon key — infra/supabase.md>
META_APP_ID=<infra/meta.md>
META_APP_SECRET=<infra/meta.md>
IG_REDIRECT_URI=https://api.banterclips.com/socials/instagram/callback
STRIPE_SECRET_KEY=<infra/stripe.md>
STRIPE_PRICE_CREATOR=<infra/stripe.md>
STRIPE_WEBHOOK_SECRET=<infra/stripe.md>
FRONTEND_URL=https://www.banterclips.com
```

Edit `/etc/caddy/Caddyfile` (replace `api.example.com`), copy a demo video:

```bash
scp backend/data/media/demo.mp4 root@<droplet-ip>:/opt/banter-clips/backend/data/media/
systemctl restart banterclips-api caddy
curl https://api.banterclips.com/health   # → {"ok":true,...}
```

### Generation worker

Real generation runs in its own process, so a deploy never interrupts a render
and a four-minute render never competes with request handling. It needs
`ffmpeg`, which the API does not.

```bash
apt-get install -y ffmpeg
cp deploy/banterclips-worker.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now banterclips-worker
journalctl -u banterclips-worker -f
```

Set `QUEUE_MODE=postgres` in the backend `.env` — without it the API keeps
running renders on its own threads and the worker sits idle.

**Watch this, not CPU:** `/health/ready` reports queue depth. A rising
`queued` with a flat `running` means no worker is alive; the API stays
perfectly healthy while every clip waits forever. Alert on
`queued > 5 for 10 minutes`.

### Housekeeping (cron, hourly)

Purges expired working files and fails clips whose render was interrupted, so
a user is never stuck watching a spinner with no way to retry.

```bash
crontab -e
0 * * * * cd /opt/banter-clips/backend && .venv/bin/python -m app.services.housekeeping
```

**Updates after a git push:**
```bash
ssh root@<droplet-ip> 'cd /opt/banter-clips && git pull && backend/.venv/bin/pip install -q -r backend/requirements.txt && systemctl restart banterclips-api banterclips-worker'
```

Restarting the worker is safe at any time: it finishes the render in flight
(systemd waits up to 3 minutes), and anything it cannot finish returns to the
queue without counting as a failed attempt.

## 2. Vercel (frontend)

1. vercel.com → Add New Project → import `mohitreddy-db/banter-clips`.
2. **Root Directory: `frontend`** (build command/output auto-detected from Vite).
3. Environment variables (Production):
   - `VITE_API_URL=https://api.banterclips.com`
   - `VITE_SUPABASE_URL=https://taphbakizdagamimbhjh.supabase.co`
   - `VITE_SUPABASE_ANON_KEY=<anon key>`
4. Deploy. Every push to `main` now auto-deploys.

## 3. Supabase dashboard (one-time)

- Auth → URL Configuration → **Site URL** = `https://www.banterclips.com`;
  add `http://localhost:5173` to Additional Redirect URLs for local dev.
- Settings → Database → note/reset the **database password** (needed for the
  droplet's `DATABASE_URL`). Store it in `infra/supabase.md`.
- Auth emails: custom SMTP via Resend (smtp.resend.com:465, user `resend`,
  password = Resend API key, sender noreply@banterclips.com) — the built-in
  mailer is rate-limited. Branded templates to paste into Auth → Templates:
  [`email-templates/`](email-templates/).

## 4. Meta dashboard (one-time)

Instagram → API setup with Instagram login → Business login settings →
OAuth redirect URIs → **add** `https://api.banterclips.com/socials/instagram/callback`
(keep the tunnel one for local dev, or remove it later).

## 5. Post-deploy smoke test

1. Open the Vercel URL → sign up with a real email → confirm → sign in.
2. Onboard → connect Instagram (real consent) → generate → publish → check
   the Reel + permalink.
3. `https://api.banterclips.com/docs` loads; `/health` returns ok.

## Costs

| Item | $ |
|---|---|
| Vercel hobby | $0 |
| Droplet basic | $6/mo |
| Supabase project | $10/mo (already active) |
| Domain | whatever you pay now |
