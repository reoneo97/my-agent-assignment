# Operator Learning Assistant — Project Memory

## What this project is
A take-home demo of an agentic AI assistant that learns behavioral patterns of a manufacturing shopfloor operator over repeated interactions. Stage 1 covers the core learning loop with free-text memory in SQLite.

## Architecture
- **Deterministic pipeline** in `pipeline.py` — no lead/orchestrator agent, just code wiring small specialized agents.
- **Append-only SQLite** for events and memory operations. Profile is derived by *folding* the operation log (event sourcing). Never hard-delete; use SUPERSEDE.
- **Free-text memory items** with structured metadata — not a single prose blob, not Beta-Binomial.
- **Count-based confidence tiers** assigned by code rule (`memory/tiers.py`), never by the LLM.

## Key design rules (non-negotiable)
1. Tier = code rule on `evidence_count` — never LLM self-rating.
2. Append-only; supersede, never hard-delete. Profile must be reconstructable by folding the log.
3. Memory items are atomic NL statements with metadata wrapper.
4. Deterministic orchestration in `pipeline.py`; specialized typed agents; no orchestrator agent.
5. `tentative` is a first-class state — surfaces "confirm if relevant" caution in prompts.
6. Personalization is confidence-gated and asymmetric toward support.
7. Every memory item references `source_event_ids` for provenance.
8. Model via env vars (`MODEL_NAME`, `MODEL_BASE_URL`, `MODEL_API_KEY`) — never hardcoded.
9. Pure logic (tiers, fold) is unit-tested without network/API.

## Confidence tiers
- `tentative`: evidence_count < 3
- `established`: evidence_count >= 3
- `confirmed`: operator-validated flag set (manual)

Thresholds live in `config.py`.

## Tech stack
- Python 3.11+, Pydantic AI, Pydantic v2, SQLite (stdlib sqlite3), Ruff, mypy, pytest
- LLM: OpenAI-compatible hosted open-source model (Groq / Together / Fireworks / OpenRouter)

## Project layout
```
src/ola/
  domain/       # pure data models, no IO
  memory/       # store (SQLite) + tier rule
  agents/       # extractor, memory_manager, responder, provider
  personalization/  # render.py
  pipeline.py
  config.py
sim/persona.py  # LLM-simulated operator with hidden ground-truth traits
scripts/demo.py
tests/          # test_store.py, test_tiers.py (pure, no network)
```

## What is deferred to later stages
- Stage 2: Knowledge graph (Neo4j), alarm-code projection
- Stage 3: Evaluation harness, LLM-as-judge
- Reflection organ for novel pattern discovery
- Recency decay / drift weighting
- UI (Streamlit)
