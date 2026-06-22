#!/usr/bin/env bash
# One-time setup for a fresh Digital Ocean Ubuntu droplet.
# Run as root: bash setup-droplet.sh
set -euo pipefail

REPO_URL=${1:?"Usage: $0 <git-repo-url>"}

# ── Docker ────────────────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

# ── Clone repo ────────────────────────────────────────────────────────────────
git clone "$REPO_URL" /opt/ola
mkdir -p /opt/ola/data

# ── .env ─────────────────────────────────────────────────────────────────────
cp /opt/ola/.env.example /opt/ola/.env
echo ""
echo "✓ Docker installed"
echo "✓ Repo cloned to /opt/ola"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/ola/.env — set MODEL_API_KEY"
echo "  2. Add these secrets to your GitHub repo:"
echo "       DROPLET_HOST    = <droplet IP>"
echo "       DROPLET_USER    = root"
echo "       DROPLET_SSH_KEY = <private key that can SSH into the droplet>"
echo "  3. Push to main — the workflow handles everything from there."
