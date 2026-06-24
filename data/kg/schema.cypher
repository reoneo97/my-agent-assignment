// ── Operator Learning Assistant — Neo4j Schema ───────────────────────────────
// Run once on a fresh database. All constraints are idempotent (IF NOT EXISTS).

// ── Uniqueness constraints ────────────────────────────────────────────────────

CREATE CONSTRAINT machine_type_name IF NOT EXISTS
FOR (n:MachineType) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT machine_id IF NOT EXISTS
FOR (n:Machine) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT alarm_code_code IF NOT EXISTS
FOR (n:AlarmCode) REQUIRE n.code IS UNIQUE;

CREATE CONSTRAINT procedure_id IF NOT EXISTS
FOR (n:Procedure) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT procedure_step_id IF NOT EXISTS
FOR (n:ProcedureStep) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT skill_name IF NOT EXISTS
FOR (n:Skill) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT modality_name IF NOT EXISTS
FOR (n:Modality) REQUIRE n.name IS UNIQUE;

CREATE CONSTRAINT operator_id IF NOT EXISTS
FOR (n:Operator) REQUIRE n.id IS UNIQUE;

// ── Indexes for frequent lookups ──────────────────────────────────────────────

CREATE INDEX alarm_category IF NOT EXISTS FOR (n:AlarmCode) ON (n.category);
CREATE INDEX alarm_severity IF NOT EXISTS FOR (n:AlarmCode) ON (n.severity);
CREATE INDEX machine_line   IF NOT EXISTS FOR (n:Machine)   ON (n.line);
CREATE INDEX operator_shift IF NOT EXISTS FOR (n:Operator)  ON (n.shift);

// ── Wave 2 learned-behaviour edge property indexes ────────────────────────────
// (evidence_count and last_updated queried frequently by the projection job)

CREATE INDEX rel_prefers_count     IF NOT EXISTS FOR ()-[r:PREFERS]-()      ON (r.evidence_count);
CREATE INDEX rel_confident_count   IF NOT EXISTS FOR ()-[r:CONFIDENT_WITH]-() ON (r.evidence_count);
CREATE INDEX rel_struggles_count   IF NOT EXISTS FOR ()-[r:STRUGGLES_WITH]-() ON (r.evidence_count);
