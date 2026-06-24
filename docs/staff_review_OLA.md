# Staff Engineering Review — Operator Learning Assistant (OLA)

*Reviewer perspective: staff engineer, agentic systems. Scope of review: `PRD_v2.md`, `agent_design.md`, `api_ui.md`, `data_schema.md`. This is a design review of a 7-day demo build, with explicit attention to what changes when the system leaves the demo and serves many operators across many sites.*

---

## 0. What the system is (so the critique has a frame)

OLA learns a behavioural profile of factory-floor operators by watching their interactions with an assistant. The core idea is genuinely good and worth protecting: it reasons over the **gap between work-as-imagined (manuals/SOPs in a Neo4j KG) and work-as-done (interactions/outcomes in SQLite)**. Four small hot-path agents (Extractor, Memory Manager, Responder) plus a per-shift Reviewer do the LLM work; everything load-bearing — tier promotion, KG projection, conformance routing — is deterministic code. The append-only `memory_operations` log as the single source of truth, with the profile *derived by folding* it, is the strongest architectural decision in the whole spec. It gives replayability, auditability, and correctability for free.

The critique below is not an attack on that spine. It is an attempt to find where the spine bends under load.

---

## 1. Weaknesses in the initial design

### 1.1 The tier rule is a counter, and counters are gameable by correlated evidence
`evidence_count >= 3 → established` treats every observation as independent. It is not. An operator who asks for visual steps four times **in one session about one alarm** is one piece of evidence repeated, not four. The current rule will promote that belief to `established`, project it into the KG, and start *reducing scaffolding* for that operator — on the strength of a single afternoon. This is the classic "pseudo-replication" failure. The PRD acknowledges tiers are "heuristic, not calibrated," but the heuristic has a specific exploitable shape: **temporal and contextual clustering inflates confidence**. At minimum, dedupe evidence by `(session_id, category, value)` before counting, and prefer counting *distinct sessions* or *distinct days* over distinct events.

### 1.2 No decay means the profile can only ever be confidently wrong
Recency-decay is listed as "DESIGNED-ONLY / optional minimal." For a demo, fine. But the design has an asymmetry that makes the absence of decay worse than neutral: promotion is easy (count to 3) and the only demotion path is an explicit `SUPERSEDE` emitted by the Memory Manager when it notices a contradiction. People change — an operator gets trained, gains confidence, switches lines. If their behaviour changes gradually rather than via a single contradicting event, nothing ever fires a SUPERSEDE, and a stale `established` belief sits in the KG driving personalization indefinitely. **Established beliefs need a half-life, or at least a "last reinforced N shifts ago → demote to tentative" sweep.** Without it, the system's confidence is monotonic and reality is not.

### 1.3 Contradiction handling lives entirely in one LLM call with no tie-breaker
The PRD is honest that "contradiction handling is LLM judgment (can be inconsistent)." The deeper issue is that the Memory Manager sees `signals + current profile` and must decide ADD vs REINFORCE vs SUPERSEDE *in one shot, on the fast/cheap model*. Two failure modes:
- **Silent fragmentation**: instead of SUPERSEDE-ing a contradicting belief, the cheap model ADDs a near-duplicate ("prefers visual" + "likes diagrams"). Now evidence is split across two items, neither reaches `established`, and the profile looks indecisive. There is no de-duplication / entity-resolution step on memory items.
- **Thrash**: alternating signals cause SUPERSEDE/ADD oscillation with no hysteresis.

The count-based tier is described as the "backstop," but it does not actually backstop *fragmentation* — it makes it worse, because fragmentation starves the count. The Reviewer's per-shift consolidation is the intended cleanup, but it runs on a slow clock; in the meantime the live profile drives operator-facing behaviour.

### 1.4 The conformance 2×2 rests on an attribution model the PRD itself distrusts
`outcomes` are machine-window metrics (downtime, alarm count) compared to a `peer_alarm_avg`. The PRD flags the confound. But the 2×2 is not a peripheral feature — `divergent + good → tacit-knowledge candidate` is the headline mechanism that feeds *discovered* KG edges. If the outcome signal is noisy, the tacit-knowledge queue fills with **lucky shortcuts misread as expertise**, and the only thing standing between that noise and a permanent KG edge is the expert-validation gate — which is DESIGNED-ONLY. For the demo the window is simulated, so this is hidden. It is the single biggest correctness risk waiting at the other end of the "build it for real" decision, and it should be called out as such, not buried in §11.

### 1.5 Extractor and Memory Manager are split, but the split leaks
The Extractor is "perception only; no memory awareness." Clean separation in principle. In practice, good belief-updating often *needs* to know what's already believed to interpret an ambiguous event (the same "can you show me" means different things from a novice vs an expert). By forbidding the Extractor any memory awareness and making the Memory Manager the only context-aware step, you push all the interpretive load onto the one cheap call that is already doing the hardest reasoning (contradiction). Worth questioning whether the boundary is in the right place, or whether the Extractor should at least receive the synopsis as read-only context.

### 1.6 Operational gaps that will bite even at demo scale
- **No idempotency on the hot path.** If `/interaction` is retried (network blip, double-click), the same event is processed twice → duplicate signals → inflated counts. Append-only makes this *worse*, because you cannot delete the dupes; you can only fold around them. There is no `client_request_id` / dedup key in the `events` schema.
- **KG/SQL dual-write is not transactional.** Projection writes to Neo4j after a code rule fires on SQL state. If the SQL commit succeeds and the Neo4j upsert fails (or vice-versa), the two stores diverge with no reconciliation path described. The "FK-in-spirit, joined by ID" bridge has no integrity checker.
- **Synopsis regeneration is full-state, not incremental.** Fine at demo scale, explicitly. But it means synopsis cost grows with history length per operator — noted here because it becomes a scaling cliff in §3.
- **No schema migration story.** The profile is reconstructed by folding the log; if the *shape* of a `MemoryOperation` ever changes, every historical fold must still replay. Versioning the op format now is cheap insurance.

### 1.7 Minor inconsistencies between documents
`data_schema.md` (an earlier draft) and `PRD_v2.md` disagree in small ways the build will trip over: `data_schema` has `events.raw_text`, PRD has `events.content`; `data_schema`'s `memory_operations` lacks `source` and `high_weight` columns that the PRD's confirmation loop depends on; `data_schema`'s `conformance.conformance` is `NOT NULL` while the PRD sets it later by the Reviewer (so it must be nullable). PRD_v2 is clearly canonical — the fix is to mark `data_schema.md` superseded to stop it being a source of build ambiguity.

---

## 2. Improvements to the current agentic workflow

These are single-user / pre-scale improvements that strengthen the existing loop without violating the design's invariants.

**2.1 Make evidence independence explicit.** Change the tier rule's input from raw `evidence_count` to a **distinct-session (or distinct-day) count**, and dedup signals on `(session_id, category, value)` at fold time. This is a pure-code change, unit-testable, and directly addresses 1.1. Keep the raw count for display; gate promotion on the deduped count.

**2.2 Add a cheap decay sweep to consolidation.** During `run_consolidation()`, demote any `established` item not reinforced within *K* shifts to `tentative` (append a deterministic `DECAY` op so it stays in the replayable log — never mutate). This closes 1.2 while preserving append-only and replay. It also creates a satisfying demo beat: "watch a stale belief soften when the operator's behaviour changes."

**2.3 Give the Memory Manager an explicit merge/canonicalize step.** Before ADD, run a deterministic similarity check (embedding cosine or even normalized-text match) against existing items in the same category; route near-matches to REINFORCE instead of ADD. This is the entity-resolution the PRD admits production needs (1.3, 1.7) — pulling a *minimal* version forward kills fragmentation cheaply and keeps counts honest.

**2.4 Add hysteresis to SUPERSEDE.** Require either a `high_weight` confirmation **or** N independent contradicting signals before a SUPERSEDE actually demotes an `established`/`confirmed` belief. Prevents single-event thrash. The asymmetry already in the personalization layer ("asymmetric toward support") should be mirrored in belief stability: easy to add caution, hard to overwrite hard-won confidence.

**2.5 Idempotency key on `events`.** Add `client_request_id` (unique) and make `/interaction` upsert-by-key. Smallest possible change that prevents double-counting (1.6) and is mandatory before any retry/queue infrastructure in §3.

**2.6 Promote confirmation from binary to a small budget.** Right now the Validation Gate fires only when "tentative + support-reducing, or contradiction." Good restraint. One improvement: track a per-shift **confirmation budget** so the assistant can ask about the highest-value uncertain belief even absent a triggering event, without ever becoming naggy. This converts passive learning into gentle active learning and tightens the time-to-`confirmed`.

**2.7 Separate "reply quality" from "learning quality" in eval.** The current eval harness measures inferred-vs-ground-truth traits (precision/recall). Add a second axis: did the *personalization directive* actually change the reply in a way an operator would feel? A correct belief that never changes behaviour is worthless; a wrong belief that drives bad scaffolding is harmful. A/B the directive on/off against persona satisfaction. This is the metric that justifies the whole system existing.

**2.8 Make the Extractor synopsis-aware (read-only).** Per 1.5, feed the operator synopsis into the Extractor as immutable context so ambiguous events are typed correctly, while keeping the hard invariant that the Extractor still emits only perception and writes nothing.

---

## 3. Scaling to multiple users — the hard part

The demo is one operator, one process, a manual "End Shift" button, full-state synopsis regeneration, and a fold-on-every-read profile. Each of those is a deliberate, correct demo choice **and** a scaling cliff. Below: what breaks, why, and a deployment design.

### 3.1 What actually gets harder at scale (and what doesn't)

**The genuinely easy part: read/serving scale.** The hot path is per-operator and embarrassingly parallel. Operators don't share session state. So horizontal scaling of the *serving* tier is straightforward. This should be said plainly because it lets us focus on the three things that are genuinely hard.

**Hard problem 1 — Correctness under concurrency and the fold.**
- *Fold cost.* The profile is recomputed by folding the entire `memory_operations` log on every read. One operator, one shift: trivial. Ten thousand operators with two years of history: the fold is now the dominant latency term on the hot path, and it grows monotonically because the log is append-only and never compacted. **This is the first thing that falls over.**
- *Concurrent writes.* A live operator interacting while the Reviewer consolidates that same operator's history is a read-modify-write race on a derived structure. SQLite's single-writer model hides this in the demo; a real multi-writer store exposes it. The fold and the consolidation can disagree about "current profile."
- *Cross-store consistency.* SQL→KG projection at scale means thousands of small Neo4j upserts racing with reads from the Context Assembler. Dual-write divergence (1.6) goes from "unlikely in a demo" to "happens daily."

**Hard problem 2 — Knowledge collapse / contamination across operators.**
This is the subtle one and the most important to get right. The demo keeps everything per-`operator_id`, which is safe. The *value* of the system, though, pushes toward sharing: the `RELATED_TO` confidence transfer, the *discovered* tacit-knowledge edges (`ALSO_RESOLVED_BY`), the collective hypotheses (`operator_id = null`). The moment learning crosses operator boundaries, three collapse modes appear:
  - **Homogenization / regression to the mean.** If discovered tacit knowledge from strong operators is fed back as default guidance to everyone, the population's behaviour converges toward a single learned policy. You lose the diversity that *generated* the tacit knowledge in the first place — the next genuine shortcut never surfaces because everyone now follows the consolidated SOP. The system erodes the very signal it feeds on.
  - **Feedback-loop contamination (model-eats-its-own-output).** Discovered edges change the assistant's guidance → operators follow the new guidance → their conformant-with-the-new-edge behaviour is observed as *more evidence* for the edge. Confidence inflates with no new ground truth. This is the classic autophagy / "model collapse" loop, and OLA is structurally exposed to it because observed behaviour is partly *caused by* the system's own prior output.
  - **Majority tyranny over legitimate minorities.** Night shift, a specific machine vintage, or a rare recipe may have genuinely different correct behaviour. Pooled learning treats their divergence as noise and trains it out. Correct-but-rare gets punished.

**Hard problem 3 — Latency and cost under load.**
- Three LLM calls on the hot path (Extractor, Memory Manager, Responder), even on the fast model, set a floor on per-interaction latency and a per-interaction $ cost that multiplies by operator count × interactions/shift. The Responder is the only one the operator waits on; the other two could in principle be moved off the blocking path.
- Per-shift `run_consolidation()` on the strong model, full-state synopsis regeneration, run for every operator at shift boundary = a **thundering herd**: thousands of expensive strong-model calls all firing at 06:00 when day shift starts. Cost and rate-limits both spike on a schedule.

### 3.2 Proposed deployment & reliability design

The shape: keep the demo's invariants (append-only truth, deterministic writes, agents-decide-code-writes), and add the infrastructure those invariants were quietly assuming. Diagram in prose:

**Ingress → stateless API tier (FastAPI, N replicas) behind a load balancer.** Sticky routing by `operator_id` (consistent hashing) so an operator's in-flight session lands on the same replica and a warm profile cache. The API tier stays the "thin shell" the design already mandates — all logic remains in `src/ola/`.

**Hot path, restructured around what the operator actually waits for.**
- Operator waits **only** on the Responder. Extractor and Memory Manager move to an **async, post-response** path: persist the raw event synchronously (cheap, this is the system of record), return the reply, then run Extractor → Memory Manager off the critical path via a durable queue (e.g. one partition per `operator_id` to preserve ordering). Learning becomes eventually-consistent with the conversation, which is fine — the profile only needs to be current *by the next interaction*, not within the current one. This roughly thirds the operator-perceived LLM latency.
- The Context Assembler reads from a **materialized profile cache** (see below), not a live fold.

**Replace fold-on-read with an incrementally-maintained materialized profile, without giving up the log as truth.** Keep `memory_operations` as the immutable source of truth (this is non-negotiable and correct). Maintain a **derived, versioned profile snapshot** per operator that is updated incrementally as ops are appended, and is *always reconstructable* by replaying the log from the last checkpoint. This is event-sourcing with snapshots: truth stays in the log, reads hit the snapshot, and you periodically checkpoint+compact so replay cost is bounded. The PRD already gestures at "a derived cache later (Stage-2 optimisation)" — this is that cache, made authoritative-for-reads-only. Correctness test: snapshot must equal full-fold (the existing replay-equality test generalizes directly).

**Datastore choices at scale.**
- Move the system-of-record off SQLite to a single-primary Postgres (append-only tables, partitioned by `operator_id` or by time). Keeps transactional writes and gives real concurrency.
- Keep the KG in Neo4j but make **projection transactional via the outbox pattern**: the SQL transaction that crosses an item to `established` also writes a row to an `outbox` table; a separate relay applies it to Neo4j with at-least-once delivery and idempotent upserts (keyed on `source_item_id`). This is the principled fix for dual-write divergence (1.6) — SQL is the commit point, the KG is downstream and self-healing. A periodic reconciler diffs projected SQL items against KG edges and repairs drift.

**Consolidation: from "button" to a smeared, idempotent batch.**
- Trigger per-operator consolidation **staggered** across the shift-change window (jittered schedule, or driven by per-operator activity rather than a global clock) to kill the thundering herd. Better: trigger consolidation for an operator when they accumulate *enough new material*, decoupled from wall-clock shift boundaries — the shift boundary becomes one trigger among several.
- Make `run_consolidation()` idempotent and resumable (it nearly is — it's "no-op safe if nothing changed"). Run it as queue-driven workers with rate-limit-aware concurrency against the strong model, with backpressure rather than fan-out.
- Make synopsis regeneration **incremental** (summarize-on-top-of-previous-synopsis + recent delta) so its cost stops scaling with total history.

**Containing knowledge collapse (the part most worth designing carefully).**
- **Two-layer memory: personal vs collective, with a one-way validation gate between them.** Per-operator beliefs stay strictly personal and never auto-merge. Cross-operator knowledge (tacit edges, collective patterns) lives in a separate collective layer that an operator's guidance may *read* but that personal observations may only *enter* through the expert-validation gate. The gate stops being "DESIGNED-ONLY" — at scale it is the load-bearing wall against autophagy. No discovered edge becomes default guidance without a human (or a high, multi-operator, multi-outcome evidence bar) signing off.
- **Provenance-tagged evidence to break the feedback loop.** Tag every observation with whether the assistant's guidance *influenced* it (`assistant_guided` vs `unprompted`). When accruing evidence for a tacit edge or a confidence belief, **down-weight or exclude assistant-guided observations** so the system cannot confirm its own suggestions. This is the concrete defense against the model-eats-its-output loop: confidence may only grow on evidence the system did not cause.
- **Stratify, don't homogenize.** Hold collective learning at the right granularity — per machine-type, per shift, per recipe — rather than one global pool, so legitimate minorities (night shift, rare recipes) are not averaged away. Surface divergence between strata as a *signal* (maybe night shift knows something), not noise to be corrected.
- **Diversity guard.** Track behavioural variance per cohort; if consolidation is measurably collapsing variance over time, that is an alarm, not a success. Cap how strongly collective guidance overrides an individual's own established beliefs.

**Reliability & operability.**
- *Idempotency everywhere* (1.6): `client_request_id` on ingest; idempotent KG upserts; resumable consolidation. With these, every component is safe to retry, which is the precondition for queues and autoscaling.
- *Graceful degradation ladder for LLM dependency.* The fab cannot stop because an LLM endpoint is rate-limited. Degrade in order: strong model unavailable → defer consolidation (it's already out-of-band, so this is invisible to operators). Fast model unavailable for Extractor/MM → still return the Responder reply and **enqueue** learning for later (the async restructure makes this free). Responder model unavailable → fall back to the *deterministic* KG procedure content directly (the manual steps for the alarm), with a banner that personalization is degraded. The KG-as-index-over-procedure-prose design makes this fallback genuinely useful, not a dead end. **Never** let any failure add friction to escalation — the demo's "never block getting a human" rule becomes a hard SLO at scale.
- *Multi-tenancy isolation.* Per-site (and likely per-customer) data isolation: separate schemas/graphs, row-level scoping, and a noisy-neighbor budget so one site's consolidation storm can't starve another's hot path.
- *Observability tuned to this system's specific risks.* Beyond latency/error dashboards: track tier-promotion rate, SUPERSEDE rate, fragmentation (duplicate-item rate per category), KG/SQL reconciliation drift, fraction of evidence that is `assistant_guided`, and per-cohort behavioural variance. These are the leading indicators of the failure modes above; generic APM won't see them.
- *Cost controls.* Per-interaction and per-shift token budgets, cheap-model routing by default with strong-model reserved for consolidation, and prompt/result caching on the Context Assembler's KG neighborhood (it changes slowly).

### 3.3 Suggested rollout sequencing
1. **Harden single-tenant** (Section 2 fixes: dedup, decay, idempotency, merge step). These are correctness fixes that are *cheaper now than after scale-out* and several are pure-code/unit-testable.
2. **Snapshot the profile** (event-sourcing-with-checkpoints) and **make projection transactional** (outbox). Removes the two scaling cliffs (fold cost, dual-write drift) without changing semantics.
3. **Restructure the hot path** (async Extractor/MM; Responder-only blocking) and **smear consolidation**. Removes the latency floor and the thundering herd.
4. **Introduce the collective layer** behind the validation gate, with provenance-down-weighting and stratification. Only after 1–3 are stable, because this is where correctness risk is highest and it depends on everything before it being trustworthy.
5. **Pilot A/B** against real operators (the PRD's own "eventual standard") before any cross-operator guidance is trusted as default.

---

## 4. The one-paragraph version

The OLA design is well-architected for what it is — the append-only-log-as-truth, deterministic-writes, and agents-decide/code-writes invariants are exactly right and should survive contact with scale. The most pressing *correctness* weaknesses today are that confidence is a naive event counter vulnerable to correlated evidence, that beliefs can only ever grow more confident (no decay, fragile single-LLM contradiction handling), and that the conformance/tacit-knowledge pipeline rests on an outcome-attribution signal the authors themselves distrust. Most of these have cheap, in-spirit fixes (deduped distinct-session counting, a decay sweep, a merge step, idempotency keys). At scale, three things get genuinely hard: the fold-on-read profile becomes the latency bottleneck (fix: event-sourcing with snapshots, keeping the log as truth); the hot path's three blocking LLM calls and the synchronized per-shift strong-model consolidation become a cost/latency cliff (fix: make only the Responder blocking, smear consolidation, degrade gracefully); and — most importantly — any cross-operator learning invites **knowledge collapse** through homogenization, self-confirming feedback loops, and majority tyranny. The defense is a personal/collective two-layer memory separated by a real (no longer optional) validation gate, provenance-tagging to exclude the system's own influence from its evidence, and stratified rather than pooled collective knowledge. Build the single-tenant hardening first; earn the right to share knowledge across operators last.

---

*Notes on autonomy: this review was produced without access to the running code or the team — it reads the four design docs as the source of truth, treats `PRD_v2.md` as canonical where it conflicts with the earlier `data_schema.md`, and assumes the DESIGNED-ONLY items are genuinely unbuilt. `events.md` and `memory.md` in the docs folder are empty and were not used.*
