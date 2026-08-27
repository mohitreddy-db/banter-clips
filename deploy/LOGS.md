# Logs runbook

Where to look when something misbehaves, in the order that usually finds it.
Everything on the droplet logs to **journald** via systemd — there are no log
files to hunt for; `journalctl` is the one tool.

## The services

| Unit | What it is | Look here when… |
|---|---|---|
| `banterclips-api` | FastAPI backend (uvicorn :8000) | requests fail, auth issues, billing, publishing |
| `banterclips-worker` | video render worker | generation slow/failed/stuck |
| `caddy` | HTTPS reverse proxy | site unreachable, TLS errors |

```bash
ssh root@168.144.149.99 systemctl status banterclips-api banterclips-worker caddy
```

## journalctl in 30 seconds

```bash
journalctl -u banterclips-api -f                      # live tail (Ctrl-C to stop)
journalctl -u banterclips-api -n 200                  # last 200 lines
journalctl -u banterclips-api --since "1 hour ago"
journalctl -u banterclips-api --since "2026-08-14 10:00" --until "2026-08-14 11:00"
journalctl -u banterclips-api -g "stripe"             # -g = built-in grep (regex)
journalctl -u banterclips-api -u banterclips-worker --since today   # both, interleaved
```

Logs persist across restarts and reboots, so yesterday's failure is still
there. Add `--no-pager` when piping.

## Recipes by symptom

### A generation failed or is stuck
```bash
ssh root@168.144.149.99 'journalctl -u banterclips-worker --since "2 hours ago" -g "<clip-id>"'
```
No clip id? Tail the worker and find the take:
```bash
ssh root@168.144.149.99 'journalctl -u banterclips-worker -n 300'
```
The worker logs every stage, per-scene attempts/costs, storage uploads and the
final `clip <id> finished in Ns ok=True cost=$X`. The pipeline's own artifacts
(plan, per-scene notes, result.json) are on disk at
`/opt/banter-clips/backend/data/work/<clip-id>/` — the finished `final.mp4`
lives there too, which is how clips were recovered when a storage upload
flaked. Deeper provenance (per-scene review verdicts, model versions, cost) is
in the DB: `clips.provenance`.

### Payments / upgrade issues
1. Our side: `journalctl -u banterclips-api --since today -g "stripe|billing|webhook"`
2. Stripe's side (usually more telling):
   - **Developers → Webhooks → endpoint** — every delivery, its response code,
     and pending retries. Our API returning 400 here = signing-secret mismatch.
   - **Developers → Logs** — every API call we made, with full error bodies.
   - **Developers → Events** — what actually happened (sub created, payment failed…).

### Instagram publish failed
```bash
ssh root@168.144.149.99 'journalctl -u banterclips-api --since today -g "publish|instagram|graph"'
```
Remember Meta *fetches* the video from our public URL — a publish failure can
be a media-serving problem, not a Graph API one; check for the media request
in the same window.

### Sign-in problems
1. `journalctl -u banterclips-api --since today -g "auth|supabase"`
2. Supabase dashboard → Logs → **Auth** (bad passwords, rate limits, the
   circuit breaker we hit once lives here).

### Site down / certificate errors
```bash
ssh root@168.144.149.99 'journalctl -u caddy -n 100'
```
ACME/renewal errors here usually mean a Cloudflare record went orange-cloud —
every record must be DNS-only (grey). Frontend down but API fine → Vercel
dashboard → banter-clips-v2 → Deployments → latest → Logs.

### After a deploy, is everything actually up?
```bash
ssh root@168.144.149.99 'systemctl is-active banterclips-api banterclips-worker && journalctl -u banterclips-api -n 20'
curl -s https://api.banterclips.com/health
```
Boot logs show the additive DB migrations applying — a migration failure is
logged but never blocks boot.

## Other planes, quick reference

- **Vercel (frontend)**: dashboard → banter-clips-v2 → Deployments → Logs.
  Build failures only; the served site is static.
- **Supabase**: dashboard → Logs — Auth for sign-ins, Postgres for slow/failed
  queries, Storage for upload errors.
- **Stripe**: see the payments recipe above.
- **Local dev**: API + worker log to the terminal running them; local Postgres:
  `docker logs banterclips-postgres`.

## Notes

- The user-facing progress line (`clips.current_step`) is deliberately vague;
  costs, retry counts and internals only ever appear in the worker journal.
- journald caps disk usage itself (`journalctl --disk-usage` to check); no
  logrotate to maintain.
- Grep is your friend across units: when in doubt,
  `journalctl -u banterclips-api -u banterclips-worker --since today -g "<anything>"`.
