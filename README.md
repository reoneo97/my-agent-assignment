# Operator Learning Assistant — Stage 1

An agentic AI assistant that learns the behavioural patterns of a manufacturing shopfloor operator over repeated interactions. It uses a deterministic learning loop backed by free-text memory in SQLite, driven by a simulated operator persona.

## Architecture

```
Persona simulator
    ↓ OperatorInteraction
Ingest (append-only SQLite)
    ↓
Extractor agent → BehaviouralSignals
    ↓
Memory Manager agent → MemoryOperations (ADD / REINFORCE / SUPERSEDE / NOOP)
    ↓
Apply ops (append-only) → Fold log → OperatorProfile
    ↓
Render profile block + Directive (code rule, not LLM)
    ↓
Responder agent → Personalized reply
```

Key design principles:
- **Append-only SQLite** — events and memory operations are never deleted; profile is fully reconstructable by folding the log.
- **Count-based confidence tiers** — `tentative` (n<3) / `established` (n≥3) / `confirmed` (manual) — set by code, never by LLM.
- **Confidence-gated personalization** — scaffolding reduced only for established items; tentative items surface "confirm if relevant" caution.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js 20+](https://nodejs.org) (for the React UI)
- Docker + Docker Compose (for containerized runs)
- An [OpenRouter](https://openrouter.ai) API key

## Setup

```bash
# 1. Clone / enter the repo
cd my-agent-assignment

# 2. Install all dependencies (Python + Node)
make install

# 3. Configure environment
cp .env.example .env
# Edit .env — set MODEL_API_KEY to your OpenRouter API key
```

## Running locally (dev)

```bash
# Terminal 1 — FastAPI backend with hot reload
make api

# Terminal 2 — React UI at http://localhost:5173
make ui

# The Vite dev server proxies /api → http://localhost:8000 automatically.
```

```bash
# Run the CLI demo instead (10 interactions by default)
make demo
make demo N=5

# Run tests only (no network required)
make test
```

## Running with Docker

```bash
# Build API + UI images
make build

# Start both services
#   API  → http://localhost:8000
#   UI   → http://localhost:3000
make up

# Stop
make down
```

```bash
# Run the CLI demo via Docker (uses the 'demo' Compose profile)
make demo-docker
N=5 make demo-docker
```

The SQLite database is persisted to `./data/ola.db` on the host via a volume mount, so the operator profile survives across container restarts.

## Development

```bash
make lint        # ruff check
make lint-fix    # ruff check --fix
make typecheck   # mypy
make check       # lint + typecheck
make test        # pytest (pure, no network)
make clean       # remove .venv, node_modules, caches, *.db
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MODEL_NAME` | `meta-llama/llama-3.3-70b-instruct` | OpenRouter model ID |
| `MODEL_BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible base URL |
| `MODEL_API_KEY` | _(required)_ | OpenRouter API key |
| `OLA_DB_PATH` | `ola.db` | SQLite database path |

## Project structure

```
api/
  main.py              # FastAPI app — /api/chat (SSE), /api/profile/{id}
ui/
  src/
    App.tsx            # layout: profile sidebar + chat window
    api.ts             # fetch-based SSE client
    types.ts           # shared TypeScript types
    components/
      ChatWindow.tsx   # message list, streaming input, memory op badges
      ProfilePanel.tsx # live operator profile with tier badges
  Dockerfile           # nginx serving the Vite build, proxies /api
  nginx.conf           # SSE-safe proxy config
src/ola/
  config.py              # thresholds + env var reads
  pipeline.py            # deterministic orchestration (Stage-2 seam)
  domain/
    events.py            # OperatorInteraction
    signals.py           # BehaviouralSignal, TraitCategory
    memory.py            # MemoryItem, MemoryOperation, OperatorProfile
  memory/
    store.py             # append-only SQLite + deterministic fold → profile
    tiers.py             # pure assign_status() — code rule, never LLM
  agents/
    provider.py          # OpenRouter via OpenAI-compatible interface
    extractor.py         # structured signal extraction agent
    memory_manager.py    # ADD/REINFORCE/SUPERSEDE/NOOP decision agent
    responder.py         # personalized response agent
  personalization/
    render.py            # confidence-gated profile block + directive
sim/
  persona.py             # LLM-simulated operator with hidden ground-truth traits
scripts/
  demo.py                # prints ops, profile tiers, and response after each step
tests/
  test_tiers.py          # pure tier rule (3 tests, no network)
  test_store.py          # fold correctness, REINFORCE, SUPERSEDE, replay (6 tests)
```

## Known limitations

- Contradiction handling is LLM judgment and can be inconsistent across runs.
- Tiers are heuristic evidence counts, not calibrated probabilities.
- Extraction can over-generalize from thin evidence — the count-based tier is the backstop.
- In production, consider [Mem0](https://github.com/mem0ai/mem0) / [Letta](https://github.com/letta-ai/letta) / [Zep](https://github.com/getzep/zep) for the memory layer; the hand-rolled store here is intentional for transparency.

## Out of scope (later stages)

- **Stage 2** — Knowledge graph (Neo4j): domain ontology + alarm-code projection as operator→entity edges.
- **Stage 3** — Evaluation harness: precision/recall vs hidden ground-truth traits; LLM-as-judge for personalization quality.
- Reflection organ for novel pattern discovery.
- Recency decay / drift weighting on the fold.
- UI (Streamlit panel showing the live profile).
