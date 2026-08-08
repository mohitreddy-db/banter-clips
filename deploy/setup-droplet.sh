#!/usr/bin/env bash
# One-time droplet setup for the BanterClips backend (Ubuntu 22.04/24.04).
# Run as root:  bash setup-droplet.sh
# Idempotent — safe to re-run.
set -euo pipefail

REPO="git@github.com:mohitreddy-db/banter-clips.git"
DIR=/opt/banter-clips

echo "── packages ──────────────────────────────────────────"
apt-get update -y
apt-get install -y python3-venv python3-pip git curl debian-keyring debian-archive-keyring apt-transport-https

# Caddy (auto-TLS reverse proxy)
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y && apt-get install -y caddy
fi

echo "── app user + code ───────────────────────────────────"
id -u banterclips &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin banterclips
if [ ! -d "$DIR/.git" ]; then
  git clone "$REPO" "$DIR"
else
  git -C "$DIR" pull
fi

echo "── python env ────────────────────────────────────────"
cd "$DIR/backend"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
mkdir -p data/media
# demo video used by dummy generation (copy once from repo assets on Vercel? no — scp it):
[ -f data/media/demo.mp4 ] || echo "!! scp a demo.mp4 to $DIR/backend/data/media/demo.mp4"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "!! Edit $DIR/backend/.env with production values (see deploy/README.md)"
fi
chown -R banterclips:banterclips "$DIR"

echo "── services ──────────────────────────────────────────"
cp "$DIR/deploy/banterclips-api.service" /etc/systemd/system/
[ -f /etc/caddy/Caddyfile.bak ] || cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak 2>/dev/null || true
cp "$DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
echo "!! Edit /etc/caddy/Caddyfile — replace api.example.com with the real domain"

systemctl daemon-reload
systemctl enable banterclips-api caddy
echo
echo "Next: edit backend/.env and /etc/caddy/Caddyfile, then:"
echo "  systemctl restart banterclips-api caddy"
echo "  curl -s https://<your-api-domain>/health"
