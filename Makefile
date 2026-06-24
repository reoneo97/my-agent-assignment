.PHONY: install sync lint lint-fix typecheck check test up down demo-docker clean

# ── Dev setup ─────────────────────────────────────────────────────────────────

install:
	uv sync --all-extras && cd ui && npm install

sync:
	uv sync

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

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	docker compose up --build

down:
	docker compose down

demo-docker:
	N=$(N) docker compose --profile demo run --rm demo

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf .venv __pycache__ .mypy_cache .ruff_cache *.db
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf ui/node_modules ui/dist
