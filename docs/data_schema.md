

## Knowledge Graph

### Wave 1 — explicit domain layer (from manuals + records, `source: MANUAL`/`RECORD`, stable)

**Nodes**
```
MachineType   {name}                                  # DieAttach, WireBond, FlipChip
Machine       {id, line, install_date}                # 5 per type
AlarmCode     {code, severity, complexity, category}  # category = mechanical|process|sensor|recipe
Procedure     {id, title}
ProcedureStep {id, order, text}                        # keep if showing step-level conformance; else drop
Skill         {name}
Modality      {name}                                   # VISUAL, TEXT, VIDEO
Operator      {id, name, tenure, shift}
```

**Edges**
```
(:Machine)-[:OF_TYPE]->(:MachineType)
(:AlarmCode)-[:OCCURS_ON_TYPE]->(:MachineType)
(:AlarmCode)-[:RELATED_TO]->(:AlarmCode)       # lightweight sibling link (replaces subsystem transfer)
(:AlarmCode)-[:RESOLVED_BY]->(:Procedure)
(:Procedure)-[:HAS_STEP]->(:ProcedureStep)
(:Procedure)-[:REQUIRES_SKILL]->(:Skill)
(:Procedure)-[:AVAILABLE_IN]->(:Modality)
(:Operator)-[:CERTIFIED_FOR]->(:Skill)
```

`RELATED_TO` is the cheap stand-in for what the subsystem gave you — confidence on one alarm becomes weak evidence about an explicitly-linked sibling. Either that, or just use the shared `category` value and skip the edge; pick one and note it as an assumption. Transfer now lands per-alarm, which is fine at demo scale.

### Wave 2 — learned operator behaviour (`source: LEARNED`, mutable, projected from SQL when a memory item reaches `established`/`confirmed`)
```
(:Operator)-[:PREFERS         {confidence, evidence_count, last_updated}]->(:Modality)
(:Operator)-[:CONFIDENT_WITH  {confidence, evidence_count, last_updated}]->(:AlarmCode)
(:Operator)-[:STRUGGLES_WITH  {confidence, evidence_count, last_updated}]->(:AlarmCode)
```
These carry `valid_from`/`last_updated`, get re-projected as confidence shifts, and are removed/invalidated when a belief decays. This is also the canonical vocabulary your free-text memory items resolve into on graduation.

### Wave 3 — discovered tacit knowledge (`source: DISCOVERED`, expert-gated)
```
(:AlarmCode)-[:ALSO_RESOLVED_BY {discovered_from, validated_by, validated_at, status}]->(:Procedure)
```
Only enters after the human-validation gate; provenance properties make it auditable. (Design-it, don't-build-it for the demo.)

## SQL (SQLite, append-only system of record)

The dividing line, restated: SQL holds everything transactional and uncertain (raw events, the memory operation log, conformance/outcome); the KG holds only confident, aggregated, or expert-validated results.

```sql
-- Raw interaction stream (append-only, immutable)
events (
  id              TEXT PRIMARY KEY,
  operator_id     TEXT NOT NULL,
  timestamp       TEXT NOT NULL,
  shift           TEXT,                    -- 'day' | 'night'
  machine_id      TEXT,
  alarm_code      TEXT,                    -- FK-in-spirit to KG AlarmCode
  event_type      TEXT NOT NULL,           -- 'alarm' | 'question' | 'task'
  requested_modality TEXT,
  raw_text        TEXT NOT NULL,
  outcome         TEXT                     -- 'resolved_independently' | 'escalated' | 'unresolved'
);

-- Extracted behavioural signals (one event -> 0..n signals)
signals (
  id              TEXT PRIMARY KEY,
  source_event_id TEXT NOT NULL REFERENCES events(id),
  operator_id     TEXT NOT NULL,
  category        TEXT NOT NULL,           -- INSTRUCTION_MODALITY | ESCALATION | TROUBLESHOOTING | ...
  value           TEXT NOT NULL,           -- e.g. 'VISUAL', 'ESCALATED_FAST'
  observation     TEXT,
  timestamp       TEXT NOT NULL
);

-- Append-only memory-operation log (THE source of truth for the profile)
memory_operations (
  id              TEXT PRIMARY KEY,
  operator_id     TEXT NOT NULL,
  op_type         TEXT NOT NULL,           -- ADD | REINFORCE | SUPERSEDE | NOOP
  target_item_id  TEXT,                    -- for REINFORCE / SUPERSEDE
  text            TEXT,                    -- for ADD / SUPERSEDE
  category        TEXT,
  source_event_id TEXT REFERENCES events(id),
  timestamp       TEXT NOT NULL
);
-- The active profile is DERIVED by folding this log; no mutable profile table.
-- MemoryItem (id, text, category, status, evidence_count, source_event_ids,
-- created_at, last_reinforced_at, superseded_by) is reconstructed in code.

-- Conformance + outcome (the third dimension; feeds the review queue)
conformance_events (
  id              TEXT PRIMARY KEY,
  source_event_id TEXT NOT NULL REFERENCES events(id),
  operator_id     TEXT NOT NULL,
  alarm_code      TEXT,
  procedure_id    TEXT,
  conformance     TEXT NOT NULL,           -- 'conformant' | 'divergent'
  outcome_status  TEXT NOT NULL DEFAULT 'pending',  -- 'pending' until window resolves
  outcome_quality TEXT,                    -- 'good' | 'bad' once known
  quadrant        TEXT,                    -- derived 2x2 cell once outcome resolves
  review_due_at   TEXT,                    -- max-wait timestamp for the queue
  reviewed        INTEGER DEFAULT 0
);

-- Outcome measurements (machine-window metrics for attribution)
outcomes (
  id              TEXT PRIMARY KEY,
  conformance_event_id TEXT REFERENCES conformance_events(id),
  machine_id      TEXT NOT NULL,
  window_start    TEXT NOT NULL,
  window_end      TEXT NOT NULL,
  downtime_sec    INTEGER,
  alarm_count     INTEGER,
  peer_alarm_avg  REAL                     -- comparison baseline (note confounds)
);
```

Three things to flag rather than bury:

`conformance_events.outcome_status = 'pending'` is the mechanism for the "await the outcome before classifying" logic we discussed — the row sits pending until the outcome window resolves, then `quadrant` gets filled and divergent+good-outcome rows route to expert review. `review_due_at` is your 24h max-wait.

There are no foreign-key constraints to the KG (`alarm_code`, `machine_id`, `procedure_id`) because those entities live in Neo4j — they're FK-*in-spirit*, joined by ID across the two stores. That's the SQL↔KG bridge made literal.

And note what's deliberately absent: **no profile table.** The profile is always a fold over `memory_operations`, never a stored mutable row — that's what preserves replay and correctability. The one thing to confirm before you build is whether you're comfortable recomputing the fold on each read (fine at demo scale) or want a derived cache later (a Stage-2 optimisation, not now).