.PHONY: install sync lint lint-fix typecheck check test eval-agents eval-loop eval mlflow-ui up down clean

# ── Dev setup ─────────────────────────────────────────────────────────────────

install:
	uv sync --all-extras && cd ui && npm install

sync:
	uv sync

# ── Quality ───────────────────────────────────────────────────────────────────

lint:
	uv run python -m ruff check src tests sim scripts api eval

lint-fix:
	uv run python -m ruff check --fix src tests sim scripts api eval

typecheck:
	uv run python -m mypy src tests sim scripts api eval

check: lint typecheck

# ── Tests — deterministic, no LLM, no MLflow ─────────────────────────────────

test:
	uv run python -m pytest tests/ -v

# ── Eval — MLflow logging ─────────────────────────────────────────────────────
# Agent evals: make eval-agents
# Loop eval:   make loop-eval [OPERATOR=op-demo-01] [N=10] [SKIP_CONV=1]
# Both:        make eval

eval-agents:
	uv run python -m eval.run_agent_evals

eval-loop:
	uv run python -m eval.run_loop_evals \
		--operator-id $(or $(OPERATOR),op-demo-01) \
		--n $(or $(N),10) \
		$(if $(SKIP_CONV),--skip-conversation,)

eval: eval-agents eval-loop

mlflow-ui:
	uv run mlflow ui --backend-store-uri mlruns

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	docker compose up --build

down:
	docker compose down

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	rm -rf .venv __pycache__ .mypy_cache .ruff_cache *.db
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf ui/node_modules ui/dist mlruns
