#!/bin/sh
set -e

echo "Running OLA bootstrap..."
uv run python -m ola.bootstrap

echo "Starting API server..."
exec uv run uvicorn ola.api.app:app --host 0.0.0.0 --port 8000
