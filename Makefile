.PHONY: install sync lint lint-fix typecheck check test api ui demo build up down clean

# ── Dev setup ─────────────────────────────────────────────────────────────────

install: ui-install
	uv sync --all-extras

sync:
	uv sync

ui-install:
	cd ui && npm install

# ── Quality ───────────────────────────────────────────────────────────────────

lint:
	uv run python -m ruff check src tests sim scripts api

lint-fix:
	uv run python -m ruff check --fix src tests sim scripts api

typecheck:
	uv run python -m mypy src tests sim scripts api

check: lint typecheck

# ── Tests (no network) ────────────────────────────────────────────────────────

test:
	uv run python -m pytest tests/ -v

# ── Local dev servers ─────────────────────────────────────────────────────────

# FastAPI backend with hot reload (requires .env)
api:
	uv run uvicorn api.main:app --reload --port 8000

# React dev server — proxies /api → localhost:8000
ui:
	cd ui && npm run dev

# CLI demo (requires .env)
demo:
	uv run python scripts/demo.py $(N)

# ── Docker (single container: API + UI) ───────────────────────────────────────

# Build and start — app available at http://localhost:8000
up:
	docker compose up --build

down:
	docker compose down

# CLI demo via Docker
demo-docker:
	N=$(N) docker compose --profile demo run --rm demo

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf .venv __pycache__ .mypy_cache .ruff_cache *.db
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf ui/node_modules ui/dist
