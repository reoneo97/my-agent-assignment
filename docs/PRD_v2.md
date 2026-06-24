# PRD v2 — Operator Learning Assistant (Consolidated Build Spec)

> Supersedes the Stage-1 PRD. This is the spec Claude Code builds against. It folds in all design decisions made since v1 (knowledge graph, conformance/outcome model, synopsis, sessions, initialization phase, agent boundaries) and gives explicit schemas for SQL, the KG, agent I/O, and the end-to-end flow. Read alongside the separate **API + UI instructions** doc.

---

## 0. Scope — what is BUILT vs DESIGNED-ONLY

This is a 7-day design-thinking demo, not production. The split below is deliberate; respect it to avoid scope creep.

| Capability                                                  | Status        | Notes                                                                                                                                 |
| ----------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Hot-path agents (Extractor, Memory Manager, Responder)      | **BUILT**     | Core loop                                                                                                                             |
| Reviewer (consolidation, hypotheses, conformance, synopsis) | **BUILT**     | Background, per shift                                                                                                                 |
| Free-text memory + append-only logs + tier rule             | **BUILT**     |                                                                                                                                       |
| Operator synopsis / consolidation buffer                    | **BUILT**     | Cheap, high demo value                                                                                                                |
| Knowledge graph (Neo4j via Docker)                          | **BUILT**     | Hand-authored small graph; load-bearing                                                                                               |
| Projection (established item → KG edge)                     | **BUILT**     | Deterministic                                                                                                                         |
| Conformance 2×2 + escalation classification                 | **PARTIAL**   | Classification BUILT; outcome window **simulated/shortened** (real outcomes take time)                                                |
| Initialization phase                                        | **PARTIAL**   | Hand-authored KG + procedure content; Manual Extractor **demonstrated on 1–2 sample manuals** to prove mechanism, rest seeded by hand |
| Session / working-memory model                              | **BUILT**     | Session = one issue's resolution                                                                                                      |
| React UI + FastAPI                                          | **BUILT**     | See API/UI doc                                                                                                                        |
| Simulated operator personas (eval harness)                  | **BUILT**     | Hidden ground-truth traits                                                                                                            |
| Tutor (training-curriculum agent)                           | DESIGNED-ONLY | Learning-needs branch                                                                                                                 |
| Expert-validation gate/UI for tacit knowledge               | DESIGNED-ONLY | Human-in-the-loop                                                                                                                     |
| Agentic troubleshooting loop                                | DESIGNED-ONLY | Stage-2 autonomy                                                                                                                      |
| Image-extraction pipeline                                   | DESIGNED-ONLY | Separate proposal                                                                                                                     |
| KG re-init / diffing, embedding retrieval, recency decay    | DESIGNED-ONLY | Future work (decay optional minimal)                                                                                                  |

---

## 1. Conceptual spine — three layers, learn from the gap

The system reasons over the **gap between authored/expected knowledge and observed/actual behaviour**:

- **Authored layer** (work-as-imagined): manuals → SOPs/procedures; training records → certifications. Lives in the **KG**.
- **Observed layer** (work-as-done): operator interactions and outcomes. Lives in **SQL**.
- **Gap detection** is the value: procedures have a *conformance* gap (did the operator follow the SOP?); skills have a *proficiency* gap (is the certified operator actually good in practice?). The same machinery surfaces both.

Two design invariants enforced everywhere:
1. **Agents decide, deterministic code writes.** No agent mutates SQL or the KG directly. Agents emit structured decisions; the pipeline persists them. The **only** path into the KG's operator-belief edges is **Projection**, triggered by a memory item crossing the `established` tier (a code rule), never by an agent.
2. **Two clocks.** The **hot path** runs every interaction (fast/cheap model). **`run_consolidation()`** runs once per shift (stronger model), triggered by the UI "End Shift" button. Nothing in the hot path calls consolidation.

---

## 2. Architecture roster

### Agents (LLM — BUILT)
| Agent            | Clock      | Model  | Job                                                                                                                                   |
| ---------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| Extractor        | Hot path   | fast   | Operator interaction → typed behavioural signals (perception only; no memory awareness)                                               |
| Memory Manager   | Hot path   | fast   | Signals + current profile → memory operations (ADD/REINFORCE/SUPERSEDE/NOOP). Returns ops; pipeline persists.                         |
| Responder        | Hot path   | fast   | Context bundle + directives → single operator-facing reply (incl. confirmation questions)                                             |
| Reviewer         | Per shift  | strong | Consolidate history → pattern/tacit proposals; conformance classification; regenerate synopsis. Distinct sub-prompts within one pass. |
| Manual Extractor | Build-time | strong | Parse manuals → draft KG (structured output) + indexed procedure content                                                              |

### Deterministic components (NO LLM — BUILT)
| Component          | Job                                                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| Pipeline           | Entrypoint; owns control flow; persists agent decisions                                                                   |
| Context Assembler  | Query + concatenate session thread + profile slice + KG neighborhood into a bundle (no LLM, no compression at this scope) |
| Validation Gate    | Restraint policy: decide whether to solicit a confirmation this turn                                                      |
| Tier Rule          | evidence_count (+confirmed flag) → status                                                                                 |
| Render/Personalize | Active profile → prompt block + directive (confidence-gated, asymmetric toward support)                                   |
| Conformance Router | Does this event have an SOP to compare against? Mark evaluable + carry expected_disposition                               |
| Projection         | Established item → canonical KG edge (upsert)                                                                             |
| Outcome Resolver   | Resolve pending conformance events once outcome window elapses; fill 2×2 cell; route to review                            |

**No agent-to-agent handoff.** Agents are stateless functions; the pipeline sequences them.

---

## 3. SQL schema (SQLite, append-only system of record)

```sql
-- Full session record, both sides of the conversation (episodic memory).
-- Append-only, immutable. Extractor reads role='operator' rows;
-- Context Assembler reads all rows for a session_id.
CREATE TABLE events (
  id                 TEXT PRIMARY KEY,
  operator_id        TEXT NOT NULL,
  session_id         TEXT NOT NULL,
  role               TEXT NOT NULL,        -- 'operator' | 'assistant'
  timestamp          TEXT NOT NULL,
  shift              TEXT,                  -- 'day' | 'night'
  machine_id         TEXT,                  -- null for assistant rows
  alarm_code         TEXT,                  -- FK-in-spirit to KG AlarmCode; null if none
  event_type         TEXT NOT NULL,         -- 'alarm'|'question'|'task'|'reply'|'confirmation_response'
  requested_modality TEXT,                  -- if operator expressed one
  content            TEXT NOT NULL,         -- raw message text
  outcome            TEXT                   -- 'resolved_independently'|'escalated'|'unresolved'|null
);

-- Session = resolution of one issue. Scopes working memory.
CREATE TABLE sessions (
  id                 TEXT PRIMARY KEY,
  operator_id        TEXT NOT NULL,
  opened_at          TEXT NOT NULL,
  closed_at          TEXT,                  -- null while open
  trigger_alarm_code TEXT,
  machine_id         TEXT,
  status             TEXT NOT NULL          -- 'open'|'resolved'|'escalated'
);

-- Extractor output. One event -> 0..n signals.
CREATE TABLE signals (
  id                 TEXT PRIMARY KEY,
  source_event_id    TEXT NOT NULL REFERENCES events(id),
  operator_id        TEXT NOT NULL,
  category           TEXT NOT NULL,         -- INSTRUCTION_MODALITY|ESCALATION|TROUBLESHOOTING|SHIFT_PATTERN|LEARNING_NEED|ISSUE_CONFIDENCE
  value              TEXT NOT NULL,         -- e.g. 'VISUAL','ESCALATED_FAST','RESOLVED_INDEPENDENT'
  observation        TEXT,                  -- short NL note
  timestamp          TEXT NOT NULL
);

-- Append-only memory-operation log = SOURCE OF TRUTH for the profile.
-- The active profile (MemoryItems) is DERIVED by folding this log. No mutable profile table.
CREATE TABLE memory_operations (
  id                 TEXT PRIMARY KEY,
  operator_id        TEXT NOT NULL,
  op_type            TEXT NOT NULL,         -- ADD|REINFORCE|SUPERSEDE|NOOP
  target_item_id     TEXT,                  -- for REINFORCE/SUPERSEDE
  text               TEXT,                  -- free-text belief CONTENT for ADD/SUPERSEDE (human-facing)
  value              TEXT,                  -- structured normalized value, carried from the signal
                                            --   (e.g. 'VISUAL'); machine-facing: drives projection,
                                            --   lexical matching, and contradiction detection
  category           TEXT,
  source_event_id    TEXT REFERENCES events(id),
  source             TEXT NOT NULL,         -- 'hot_path' | 'reviewer'
  high_weight        INTEGER DEFAULT 0,     -- 1 if from a confirmation response
  timestamp          TEXT NOT NULL
);

-- Derived cache (mutable, regenerated from state). Not a source of truth.
CREATE TABLE operator_synopsis (
  operator_id        TEXT PRIMARY KEY,
  text               TEXT NOT NULL,
  generated_at       TEXT NOT NULL,
  source_through     TEXT,                  -- latest event timestamp reflected
  version            INTEGER NOT NULL
);

-- Conformance events: created by Conformance Router (pending), resolved by Outcome Resolver.
CREATE TABLE conformance_events (
  id                  TEXT PRIMARY KEY,
  source_event_id     TEXT NOT NULL REFERENCES events(id),
  operator_id         TEXT NOT NULL,
  alarm_code          TEXT,
  procedure_id        TEXT,
  expected_disposition TEXT,                -- 'SELF_RESOLVE'|'ESCALATE'|'EITHER' (from KG)
  observed_action     TEXT,                 -- what the operator actually did
  conformance         TEXT,                 -- 'conformant'|'divergent' (set by Reviewer)
  outcome_status      TEXT NOT NULL DEFAULT 'pending',  -- 'pending'|'resolved'
  outcome_quality     TEXT,                 -- 'good'|'bad'|null
  quadrant            TEXT,                 -- derived 2x2 cell once resolved
  review_due_at       TEXT,                 -- max-wait timestamp
  reviewed            INTEGER DEFAULT 0
);

-- Outcome measurements feeding the 2x2 (attribution noted as a limitation).
CREATE TABLE outcomes (
  id                  TEXT PRIMARY KEY,
  conformance_event_id TEXT REFERENCES conformance_events(id),
  machine_id          TEXT NOT NULL,
  window_start        TEXT NOT NULL,
  window_end          TEXT NOT NULL,
  downtime_sec        INTEGER,
  alarm_count         INTEGER,
  peer_alarm_avg      REAL,                 -- baseline (confounds noted)
  recurred            INTEGER               -- did the specific issue recur
);

-- Reviewer proposals: novel behavioural patterns + tacit-knowledge candidates.
CREATE TABLE hypotheses (
  id                  TEXT PRIMARY KEY,
  operator_id         TEXT,                 -- null for collective/process-level
  kind                TEXT NOT NULL,        -- 'behavioural_pattern'|'tacit_knowledge'
  description         TEXT NOT NULL,
  evidence_count      INTEGER DEFAULT 1,
  status              TEXT NOT NULL,        -- 'proposed'|'accepted'|'rejected'|'promoted'
  source_event_ids    TEXT,                 -- JSON array
  created_at          TEXT NOT NULL
);
```

**Derived `MemoryItem`** (reconstructed in code by folding `memory_operations`, never stored):
```
MemoryItem { id, operator_id, text, value, category,
  status: 'tentative'|'established'|'confirmed'|'superseded',
  evidence_count, source_event_ids, created_at, last_reinforced_at, superseded_by }
```
`text` is free-text belief content (human-facing: synopsis, Responder context, interpretability).
`value` is the structured normalized value carried from the originating signal (machine-facing:
drives projection, lexical eval matching, and contradiction detection). Both are kept; `value`
is never re-derived from `text`.

**Tier rule** (pure, config-driven, unit-tested; LLM never sets this):
```
confirmed   if operator-validated (a high_weight confirm op exists)
established  if evidence_count >= TIER_ESTABLISHED (default 3)
tentative    otherwise
superseded   if a SUPERSEDE op targets it
```

`alarm_code`, `machine_id`, `procedure_id` are **FK-in-spirit to the KG** — joined by ID across stores, no DB-level FK (those entities live in Neo4j).

---

## 4. Knowledge Graph schema (Neo4j)

Every node and edge carries `source ∈ {MANUAL, RECORD, LEARNED, DISCOVERED}`. MANUAL/RECORD edges are stable; LEARNED/DISCOVERED are mutable and carry provenance + temporal metadata.

### Wave 1 — domain (from manuals + training records; stable)
**Nodes**
```
(:MachineType   {name})
(:Machine       {id, line, install_date})
(:AlarmCode     {code, severity, complexity, category, expected_disposition})
                 // category ∈ mechanical|process|sensor|recipe
                 // expected_disposition ∈ SELF_RESOLVE|ESCALATE|EITHER
(:Procedure     {id, title, content_ref})   // content_ref → prose/SKILL.md payload
(:ProcedureStep {id, order, text})           // step-level (enables conformance localization)
(:Skill         {name})
(:Modality      {name})                       // VISUAL|TEXT|VIDEO
(:Operator      {id, name, tenure, shift})
```
**Edges**
```
(:Machine)-[:OF_TYPE]->(:MachineType)
(:AlarmCode)-[:OCCURS_ON_TYPE]->(:MachineType)
(:AlarmCode)-[:RELATED_TO]->(:AlarmCode)        // sibling link for confidence transfer
(:AlarmCode)-[:RESOLVED_BY]->(:Procedure)
(:Procedure)-[:HAS_STEP]->(:ProcedureStep)
(:Procedure)-[:REQUIRES_SKILL]->(:Skill)
(:Procedure)-[:AVAILABLE_IN]->(:Modality)
(:Operator)-[:CERTIFIED_FOR]->(:Skill)
```

### Wave 2 — learned operator beliefs (projected from SQL on `established`; mutable)
```
(:Operator)-[:PREFERS        {confidence, evidence_count, last_updated, source_item_id, valid_from}]->(:Modality)
(:Operator)-[:CONFIDENT_WITH {confidence, evidence_count, last_updated, source_item_id, valid_from}]->(:AlarmCode)
(:Operator)-[:STRUGGLES_WITH {confidence, evidence_count, last_updated, source_item_id, valid_from}]->(:AlarmCode)
```
Re-projected as confidence shifts; removed/invalidated when a belief decays below threshold or is superseded.

**Projection is deterministic** (no prose parsing, no LLM): it maps the established item's
`(category, value)` to an edge type + target node — e.g. `INSTRUCTION_MODALITY` + `VALUE=VISUAL`
→ `(:Operator)-[:PREFERS]->(:Modality {name:'VISUAL'})`; `ISSUE_CONFIDENCE` + an alarm value
→ `CONFIDENT_WITH`/`STRUGGLES_WITH` on that `:AlarmCode`. Because `value` is structured, this is
a lookup, which is what makes the KG-side eval lexical/exact.

### Wave 3 — discovered tacit knowledge (expert-gated; DESIGNED-ONLY for build)
```
(:AlarmCode)-[:ALSO_RESOLVED_BY {discovered_from, validated_by, validated_at, status}]->(:Procedure)
```

### Key runtime queries (Context Assembler / personalization / escalation)
```cypher
// Situation context for an alarm
MATCH (a:AlarmCode {code:$code})-[:RESOLVED_BY]->(p:Procedure)
OPTIONAL MATCH (p)-[:AVAILABLE_IN]->(m:Modality)
OPTIONAL MATCH (p)-[:REQUIRES_SKILL]->(s:Skill)
OPTIONAL MATCH (a)-[:RELATED_TO]->(sib:AlarmCode)
RETURN a.expected_disposition, a.complexity, p, collect(DISTINCT m), collect(DISTINCT s), collect(DISTINCT sib)

// Confidence transfer to an unseen sibling
MATCH (:Operator {id:$op})-[c:CONFIDENT_WITH]->(:AlarmCode)-[:RELATED_TO]->(target:AlarmCode {code:$code})
RETURN c.confidence

// Who to escalate to (skill + availability)
MATCH (a:AlarmCode {code:$code})-[:RESOLVED_BY]->(:Procedure)-[:REQUIRES_SKILL]->(s:Skill)
MATCH (expert:Operator)-[:CERTIFIED_FOR]->(s)
WHERE expert.shift = $current_shift AND expert.id <> $op
RETURN expert
```

---

## 5. Agent I/O schemas (Pydantic v2)

```python
# ---- Extractor ----
# in: one operator event (the row)  ->  out:
class BehaviouralSignal(BaseModel):
    category: TraitCategory          # enum
    value: str                       # normalized, e.g. "VISUAL"
    observation: str                 # short NL
    source_event_id: str
ExtractorOutput = list[BehaviouralSignal]

# ---- Memory Manager ----
# in: signals + current active MemoryItems  ->  out:
class MemoryOperation(BaseModel):
    op_type: Literal["ADD","REINFORCE","SUPERSEDE","NOOP"]
    target_item_id: str | None       # REINFORCE/SUPERSEDE
    text: str | None                 # ADD/SUPERSEDE — free-text belief content
    value: str | None                # ADD/SUPERSEDE — structured value, CARRIED from the signal
    category: TraitCategory | None
    source_event_id: str
    rationale: str                   # brief, for auditability
MemoryManagerOutput = list[MemoryOperation]   # pipeline persists; agent does NOT write
# Note: `value` is carried from the originating BehaviouralSignal, never re-derived.
# Reconciliation uses it: same category + same value -> REINFORCE; same category +
# different value -> SUPERSEDE (contradiction). target_item_id must match an existing item.

# ---- Responder ----
class ContextBundle(BaseModel):      # built by Context Assembler (deterministic)
    operator_message: str
    session_thread: list[dict]       # prior turns this session, both roles, verbatim
    synopsis: str | None
    relevant_profile_items: list[dict]   # tier-tagged
    kg_context: dict                 # procedure, disposition, modalities, related alarms, skills
    personalization_directive: str
    validation_directive: str | None
ResponderOutput = str                # the reply (assistant turn, persisted by pipeline)

# ---- Reviewer (distinct sub-tasks within one pass) ----
# consolidate: in (recent events + current profile) -> (list[MemoryOperation], list[Hypothesis])
# conformance: in (conformance_event + procedure steps + observed actions) ->
class ConformanceResult(BaseModel):
    conformance: Literal["conformant","divergent"]
    observed_action: str
    rationale: str
# synopsis:    in (current profile + recent events) -> str

# ---- Manual Extractor (build-time) ----
# in: manual doc (text + metadata)  ->  out:
class KGDraft(BaseModel):
    nodes: list[dict]                # typed, with properties
    edges: list[dict]                # typed, with source=MANUAL
    procedure_contents: list[dict]   # {procedure_id, content_ref, prose, image_refs}
```

---

## 6. Flows

### 6.1 Initialization (build-time, run once)
```
1. Create SQL tables.
2. Manual Extractor parses sample manual(s) -> KGDraft (structured) + procedure contents.
3. Seed non-manual nodes from mock records: Operators, CERTIFIED_FOR Skills, Machines, shifts.
4. Populate alarm metadata not in manuals (expected_disposition, complexity) — authored where absent.
5. Validation gate: hand-verify the (small) extracted KG before activation. [expert sign-off = DESIGNED-ONLY at scale]
6. Activate: reviewed KG + procedure contents go live.
```
SKILL.md = prose payload (procedure content); KG = the index over it (`Procedure.content_ref`). One source of procedure content, addressed by the graph — not two parallel copies.

### 6.2 Hot path (per interaction — fast model)
```
1. Operator event arrives -> open or continue a session -> append to events(role=operator).
2. Extractor(event) -> signals -> append to signals.
3. Memory Manager(signals, current profile) -> memory_operations (carrying each signal's structured
   `value`) -> pipeline appends to log. Reconciliation uses `value`: same category+value -> REINFORCE;
   same category, different value -> SUPERSEDE.
4. Tier rule recomputes item statuses; if an item crosses 'established' -> Projection (deterministic
   `(category, value)` -> edge lookup, no prose parsing) -> KG upsert.
5. Conformance Router: if alarm has a RESOLVED_BY procedure in KG, create a PENDING conformance_event
   (carry expected_disposition).
6. Context Assembler builds ContextBundle (session thread + profile slice + synopsis + KG neighborhood).
7. Validation Gate(profile, situation) -> validation_directive (ask only if tentative+support-reducing, or contradiction).
8. Render/Personalize(profile) -> personalization_directive (confidence-gated, asymmetric toward support).
9. Responder(bundle) -> reply -> append to events(role=assistant).
10. Return reply + updated profile (+ signals/ops for the transparency panel).
```
**Confirmation loop:** if a prior turn set a validation_directive and the operator answers, the pipeline tags that event `confirmation_response`; the Memory Manager treats it as `high_weight` evidence → promotes the item to `confirmed` or supersedes it.

**Session close:** an outcome event (resolved/escalated) sets `sessions.status` and `closed_at`. Next unrelated issue opens a new session.

### 6.3 Shift consolidation (`run_consolidation()` — per shift, "End Shift" button, strong model)
```
1. Reviewer.consolidate(recent events, profile) -> proposed memory_operations + hypotheses -> persist.
2. Outcome Resolver: for PENDING conformance_events whose window elapsed (window SIMULATED/shortened),
   compute outcome_quality from outcomes -> set quadrant -> route divergent+good-outcome to review queue.
3. Reviewer.conformance(...) classifies conformant/divergent for resolved events.
4. Tier rule recompute.
5. Projection of any newly-established items.
6. Reviewer.synopsis(...) regenerates operator_synopsis FROM CURRENT STATE (not incremental) -> bump version.
7. Return before/after profile + synopsis (for the UI contrast). No-op safe if nothing changed.
```

### 6.4 Working memory (per turn, within a session)
Reconstructed, not maintained: the Context Assembler queries `events WHERE session_id=? ORDER BY timestamp` (both roles, verbatim) plus the folded profile slice and the KG neighborhood. No compression at this scope (sessions are short). Discarded after the turn; nothing learned lives only here (extraction already persisted it).

### 6.5 Conformance 2×2 (escalation is a special case)
`expected_disposition` (from KG) × `outcome_quality` (from window):
- conformant + good → competent baseline
- divergent + bad → worker error / skill gap (support/training signal)
- conformant + bad → SOP inadequate (process signal)
- divergent + good → tacit-knowledge candidate (expert-review queue) **or** lucky shortcut — disambiguated by recurrence/outcome
Escalation: self-attempting an `ESCALATE` alarm = divergent (high-severity; real-time gentle nudge, never block); over-escalating a `SELF_RESOLVE` alarm = divergent (low-severity; retrospective, gentle). **Never add friction to getting a human.**

---

## 7. Personalization

Internal scores stay in SQL; the LLM never sees raw numbers. The Render step (code) discretizes into tiers and emits a **directive**, and a tagged profile block:
```
What you know about this operator (tailor accordingly):
- [established] Prefers visual, step-by-step instructions  (12 obs)
- [established] Resolves basic die-attach alarms independently  (9/10)
- [tentative]   May need support on flip-chip faults — limited evidence, confirm if relevant
Directive: provide visual step-by-step; proactively offer escalation; confirm the flip-chip item if it comes up.
```
Rules: discretize via code (not LLM); ground each tier with evidence; `tentative`/insufficient-evidence is first-class (assistant confirms, doesn't assume); confidence-gated and **asymmetric toward support** (reduce scaffolding only when `established`/`confirmed`; default to fuller support otherwise); render only the situation-relevant slice.

---

## 8. Project structure
```
operator-learning-assistant/
├── CLAUDE.md                      # update to match v2 (free-text memory + tiers, NOT Beta-Binomial)
├── README.md                      # run instructions (backend + frontend)
├── pyproject.toml
├── .env.example                   # MODEL_NAME, MODEL_BASE_URL, MODEL_API_KEY, NEO4J_*, CORS_ORIGIN
├── docker-compose.yml             # Neo4j
├── src/ola/
│   ├── domain/                    # events, signals, memory, profile, enums — pure, no LLM
│   ├── memory/
│   │   ├── store.py               # SQLite append-only + fold -> profile
│   │   ├── tiers.py               # pure tier rule
│   │   └── synopsis.py            # synopsis read/write (cache)
│   ├── kg/
│   │   ├── client.py              # Neo4j driver wiring
│   │   ├── queries.py             # the Cypher in §4
│   │   └── projection.py          # established item -> edge (deterministic)
│   ├── agents/
│   │   ├── provider.py            # OpenAI-compatible model wiring (fast + strong)
│   │   ├── extractor.py
│   │   ├── memory_manager.py
│   │   ├── responder.py
│   │   ├── reviewer.py            # consolidate / conformance / synopsis sub-prompts
│   │   └── manual_extractor.py    # build-time
│   ├── personalization/
│   │   ├── render.py
│   │   └── validation_gate.py
│   ├── conformance/
│   │   ├── router.py
│   │   └── outcome_resolver.py
│   ├── context_assembler.py
│   ├── pipeline.py                # hot path orchestration (entrypoint)
│   ├── consolidation.py           # run_consolidation() (per-shift batch)
│   ├── init.py                    # initialization phase
│   ├── api/                       # thin FastAPI layer (see API/UI doc)
│   └── config.py                  # thresholds, env
├── sim/
│   └── persona.py                 # LLM operator w/ HIDDEN ground-truth traits (server-side only)
├── eval/                          # Task 3 harness (precision/recall vs ground truth, A/B)
├── data/manuals/                  # hand-authored sample manuals
├── scripts/seed_kg.py             # hand-authored KG + procedure content
└── tests/
    ├── test_store.py              # append-only + fold replay equality
    ├── test_tiers.py              # tier rule
    └── test_projection.py         # established gating
```

---

## 9. Non-negotiable constraints
1. Agents decide, code writes. No agent mutates SQL/KG directly. Projection is the only path into KG operator edges, gated on `established`.
2. Confidence tier = code rule on evidence_count, never LLM self-rating.
3. Append-only; supersede, never hard-delete; profile reconstructable by folding the log.
4. Deterministic orchestration in pipeline/consolidation; no lead/orchestrator agent; no agent-to-agent handoff.
5. `tentative`/insufficient-evidence is first-class and surfaces caution.
6. Personalization confidence-gated, asymmetric toward support; never add friction to escalation.
7. Provenance everywhere: memory items → source events; KG edges → `source`.
8. Persona ground-truth traits stay server-side, never an input to the pipeline, never exposed to the client (except the separated `/eval` reveal).
9. Pure logic (tiers, fold, projection gating) is dependency-free and unit-tested.
10. Model via env vars; no hardcoded keys; OpenAI-compatible provider; separate fast vs strong model config.
11. Beliefs carry BOTH a structured `value` (machine-facing: projection, lexical matching, contradiction detection) and free-text `text` (human-facing: synopsis, Responder context). `value` is carried from the originating signal and never re-derived from `text`.

---

## 10. Acceptance criteria
- End-to-end demo: simulated persona interactions flow through the hot path; profile updates visibly; KG receives an edge when an item hits `established`.
- "End Shift" runs `run_consolidation()`; UI shows before/after profile + synopsis; safe no-op on an empty shift.
- A `tentative→established` transition, a `SUPERSEDE`, and a `confirmed` (via confirmation loop) all occur across a session.
- Confidence transfer demonstrated: an unseen `RELATED_TO` alarm gets a support-leaning response from a sibling belief.
- A conformance event is classified into the 2×2 (with simulated outcome) and a divergent+good case lands in the review queue.
- Manual Extractor demonstrated on ≥1 sample manual producing KG nodes/edges + procedure content.
- Profile rebuildable purely by folding `memory_operations` (test asserts replay equality).
- Persona ground truth never reaches the client (except `/eval`); never enters the pipeline.
- `ruff` + `mypy` pass; pure-logic units pass without network.

---

## 11. Known limitations to document (README)
- Contradiction handling is LLM judgment (can be inconsistent); count-based tier is the backstop.
- Outcome attribution is noisy: downtime/alarm-count are machine-window metrics vs a single operator action; demo uses simulated/shortened windows. Production: attribute to the specific resolution; control for product/recipe/machine confounds.
- Tiers are heuristic, not calibrated probabilities (free-text choice). Primary loop-accuracy eval is **lexical** precision/recall against projected KG edges (enabled by the structured `value`); fuzzy/constrained-classification matching is reserved for pre-projection `tentative` beliefs (prose only). No ECE/Brier (free-text choice). Reliability of the lexical eval depends on projection being faithful — covered by `test_projection.py`.
- Manual→KG extraction is hand-verified at demo scale; production needs the validation gate + entity resolution.
- LLM-simulated personas are a testbed, not real operators; pilot A/B is the eventual standard.

---

## 12. Future work (deliberately cut)
KG re-init with diffing (manuals change; preserve learned edges); image-extraction pipeline (figure→step association is the hard part); embedding-based episodic retrieval at scale; recency-decay weighting on the fold; Tutor agent (learning-needs branch); expert-validation UI for tacit knowledge; agentic troubleshooting loop; skill proficiency-vs-certification gap surfacing (behaviour correcting training records).