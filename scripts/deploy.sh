#!/usr/bin/env bash
# Deploy script for the OLA droplet.
# Wipes SQLite (ephemeral learned state) and redeploys without touching named volumes.
set -euo pipefail

echo "── Pulling latest code ───────────────"
git pull origin main

echo "── Building images ───────────────────"
docker compose build

echo "── Wiping SQLite (fresh start) ───────"
rm -f data/ola.db

echo "── Starting services ─────────────────"
# --no-recreate would skip container recreation — we want the opposite:
# containers recreate (fresh SQLite), named volumes are untouched.
docker compose up -d

echo "── Done ──────────────────────────────"
echo "  App:    http://localhost:8000"
echo "  MLflow: http://localhost:5050"
echo "  Neo4j:  http://localhost:7474"
