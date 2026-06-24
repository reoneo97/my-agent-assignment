# Operator Learning Assistant — Project Memory

## What this project is
A take-home demo of an agentic AI assistant that learns the behavioural patterns of a manufacturing shopfloor operator over repeated interactions. It uses the **gap between authored knowledge (KG) and observed behaviour (SQL)** to personalise responses and surface proficiency/conformance signals.

## Two-clock architecture
- **Hot path** (every interaction, fast model): Extractor → Memory Manager → Projection → Conformance Router → Context Assembler → Validation Gate → Responder. Runs synchronously per turn.
- **Slow path** (per shift, strong model): `run_consolidation()` — Reviewer consolidate + conformance + synopsis, Outcome Resolver, Projection of newly-established items. Triggered manually by "End Shift" button; never called from the hot path.

## Non-negotiable design rules
1. **Agents decide, code writes.** No agent mutates SQL or Neo4j directly. Projection is the only path into KG operator edges, gated on `established` by code rule.
2. **Confidence tier = code rule on `evidence_count` + `high_weight` flag** — never LLM self-rating. Thresholds in `config.py`.
3. **Append-only; supersede, never hard-delete.** Profile reconstructable by folding `memory_operations` log.
4. **`tentative` is first-class** — Validation Gate surfaces caution; Responder confirms rather than assumes.
5. **Personalization is confidence-gated and asymmetric toward support** — reduce scaffolding only for `established`/`confirmed`; default to fuller support otherwise.
6. **Provenance everywhere** — memory items → `source_event_ids`; KG edges → `source` property.
7. **Persona ground-truth traits stay server-side** — never an input to the pipeline, never exposed to the client (except the separated `/api/eval` reveal endpoint).
8. **No agent-to-agent handoff** — agents are stateless functions; pipeline sequences them.
9. **Fast vs strong model split** — hot-path agents use `FAST_MODEL_NAME`; Reviewer and Manual Extractor use `STRONG_MODEL_NAME`. Both from env vars.

## Confidence tiers
| Status | Condition |
|---|---|
| `tentative` | `evidence_count < ESTABLISHED_THRESHOLD` (default 3) |
| `established` | `evidence_count >= ESTABLISHED_THRESHOLD` |
| `confirmed` | any `high_weight=True` op (from a confirmation response) |
| `superseded` | a SUPERSEDE op targets this item |

`confirmed` overrides count-based thresholds. Thresholds in `config.py`.

## SQL schema (v2, append-only system of record)
- `sessions` — one session per issue resolution. Scopes working memory.
- `events` — both operator (`role=operator`) and assistant (`role=assistant`) turns. `session_id` ties turns together. `content` is the message text (was `raw_text` in v1).
- `signals` — extractor output (one event → 0..n signals).
- `memory_operations` — THE source of truth for the profile. Fields: `source` (hot_path|reviewer), `high_weight` (1 if confirmation response), `rationale`.
- `operator_synopsis` — mutable cache (upserted by Reviewer). NOT a source of truth.
- `conformance_events` — created PENDING by Conformance Router; resolved by Outcome Resolver with 2×2 quadrant.
- `outcomes` — machine-window metrics for attribution.
- `hypotheses` — Reviewer proposals (behavioural_pattern | tacit_knowledge).

**No mutable profile table.** `MemoryItem` is always derived by folding `memory_operations`.

## Neo4j Knowledge Graph
- **Wave 1** (MANUAL/RECORD, stable): MachineType, Machine, AlarmCode, Procedure, ProcedureStep, Skill, Modality, Operator + structural edges.
- **Wave 2** (LEARNED, projected from SQL): `PREFERS→Modality`, `CONFIDENT_WITH→AlarmCode`, `STRUGGLES_WITH→AlarmCode`. Only written by `kg/projection.py` when an item crosses `established`. Never written by an agent.
- **Wave 3** (DISCOVERED, expert-gated): designed-only for the demo.

## Project layout
```
src/ola/
  domain/             # pure data models — events, signals, memory, profile, enums
  memory/
    store.py          # SQLite append-only + fold → profile; sessions; synopsis cache
    tiers.py          # pure assign_status() — never LLM
    synopsis.py       # operator_synopsis upsert/read
  kg/
    client.py         # Neo4j driver (lazy, degrades gracefully if unavailable)
    queries.py        # all Cypher — alarm context, confidence transfer, escalation
    projection.py     # established item → KG edge (deterministic, code rule gated)
  agents/
    provider.py       # make_fast_model() + make_strong_model()
    extractor.py      # hot path — interaction → BehaviouralSignals
    memory_manager.py # hot path — signals + profile → MemoryOperations (ADD/REINFORCE/SUPERSEDE/NOOP)
    responder.py      # hot path — ContextBundle → reply
    reviewer.py       # slow path — consolidate / conformance / synopsis (strong model)
    manual_extractor.py  # build-time — manual text → KGDraft + procedure contents
  personalization/
    render.py         # active profile → prompt block + personalization_directive
    validation_gate.py  # restraint policy → validation_directive (or None)
  conformance/
    router.py         # deterministic SOP check → PENDING conformance_event
    outcome_resolver.py # resolve pending events → 2×2 quadrant
  context_assembler.py  # builds ContextBundle (session thread + profile + synopsis + KG)
  pipeline.py         # hot path entrypoint — 10-step deterministic flow
  consolidation.py    # run_consolidation() — slow path, called by End Shift
  synopsis.py         # (legacy shim — use memory/synopsis.py)
  api/
    app.py            # FastAPI app, CORS, static mount; entry: ola.api.app:app
    routes.py         # thin handlers — no business logic
    schemas.py        # request/response Pydantic models
  config.py           # thresholds, env var reads (FAST_MODEL_NAME, STRONG_MODEL_NAME, NEO4J_*, ...)
sim/
  persona.py          # LLM-simulated operators w/ HIDDEN ground-truth traits
                      # get_operators() safe; get_eval_ground_truth() for /eval only
data/manuals/         # hand-authored sample manuals for Manual Extractor demo
graph/
  schema.cypher       # constraints + indexes (idempotent)
  seed.cypher         # Wave 1 seed data (MERGE — safe to re-run)
scripts/
  init_sqlite.sql     # full v2 SQL schema
  demo.py             # CLI demo driver
  setup-droplet.sh    # one-time Digital Ocean setup
eval/                 # evaluation harness (Stage 3, stub)
tests/
  test_store.py       # fold + session + high_weight + reset (pure, no network)
  test_tiers.py       # tier rule (pure, no network)
  test_projection.py  # projection gating (pure, mocked Neo4j)
ui/                   # React + TypeScript frontend (Vite)
```

## Hot path flow (pipeline.py)
1. Get or create session → attach `session_id` to interaction
2. Append operator event (`role=operator`)
3. Extractor → signals → persist to `signals`
4. Memory Manager → operations → persist to `memory_operations`; tag `high_weight` if `confirmation_response`
5. Tier recompute (fold) → Projection for newly-established items → KG upsert
6. Conformance Router → PENDING `conformance_event` if alarm has RESOLVED_BY procedure in KG
7. Context Assembler → `ContextBundle` (session thread + profile slice + synopsis + KG neighborhood)
8. Validation Gate → `validation_directive` (only when tentative item about to reduce support, or active contradiction)
9. Responder → reply
10. Append assistant event (`role=assistant`); close session if outcome set

## Slow path flow (consolidation.py / run_consolidation)
1. Reviewer.consolidate → proposed ops + hypotheses → persist
2. Outcome Resolver → resolve PENDING conformance events → fill 2×2 quadrant
3. Tier recompute → Projection of newly-established items
4. Reviewer.synopsis → regenerate `operator_synopsis` → bump version
5. Return before/after diff for UI contrast

## Key env vars
| Var | Purpose |
|---|---|
| `FAST_MODEL_NAME` | Hot-path agents (Extractor, MM, Responder) |
| `STRONG_MODEL_NAME` | Reviewer, Manual Extractor |
| `MODEL_BASE_URL` | OpenAI-compatible endpoint (default: OpenRouter) |
| `MODEL_API_KEY` | API key |
| `OLA_DB_PATH` | SQLite path |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j connection |
| `CORS_ORIGIN` | React dev server origin |

## What is designed-only (not built)
- Tutor agent (learning-curriculum from validated struggles)
- Expert-validation UI for tacit knowledge (Wave 3 KG)
- Agentic troubleshooting loop
- Image-extraction pipeline
- KG re-init / diffing, embedding retrieval, recency decay
