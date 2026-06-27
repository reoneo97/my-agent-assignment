"""
Reviewer — per-shift, strong model. Three distinct sub-tasks in one pass:
  1. consolidate: recent events + profile → proposed MemoryOperations + Hypotheses
  2. conformance: conformance_event + procedure steps + observed actions → ConformanceResult
  3. synopsis: current profile + recent events → updated operator synopsis paragraph
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_strong_model
from ola.domain.memory import Hypothesis, MemoryItem, OperatorProfile
from ola.domain.signals import TraitCategory
from ola.telemetry import agent_span

_model = make_strong_model()

# ── Sub-schemas ───────────────────────────────────────────────────────────────

class ReviewerMemoryOp(BaseModel):
    op_type: Literal["ADD", "REINFORCE", "SUPERSEDE", "NOOP"]
    target_item_id: str | None = None
    text: str | None = None
    value: str | None = None  # normalized value e.g. 'VISUAL'
    category: str | None = None
    rationale: str = ""


class ReviewerHypothesis(BaseModel):
    kind: Literal["behavioural_pattern", "tacit_knowledge"]
    description: str
    evidence_summary: str


class ConsolidateOutput(BaseModel):
    memory_operations: list[ReviewerMemoryOp]
    hypotheses: list[ReviewerHypothesis]


class ConformanceResult(BaseModel):
    conformance: Literal["conformant", "divergent"]
    observed_action: str
    rationale: str


# ── Agents ────────────────────────────────────────────────────────────────────

_consolidate_agent: Agent[None, ConsolidateOutput] = Agent(
    _model,
    name="reviewer.consolidate",
    output_type=ConsolidateOutput,
    output_retries=3,
    system_prompt="""\
You are reviewing a shift's operator interactions to update a behavioural profile.
Given recent operator events and the current profile, propose memory operations
(ADD/REINFORCE/SUPERSEDE/NOOP) to refine the profile, and flag any novel patterns
or tacit-knowledge candidates as hypotheses.

Rules:
- Only propose operations that are supported by the evidence in the events.
- SUPERSEDE when you see a clear pattern change, not just noise.
- Hypotheses are patterns not yet in the profile that recur across multiple events.
- Keep belief texts concise (one sentence).
- Your output is PROPOSED; code rules determine final tiers.
""",
)

_conformance_agent: Agent[None, ConformanceResult] = Agent(
    _model,
    name="reviewer.conformance",
    output_type=ConformanceResult,
    output_retries=3,
    system_prompt="""\
You are classifying whether an operator followed the standard procedure (SOP)
for an alarm. Compare what the operator did (observed action) against the
expected procedure steps. Be specific and fair — deviations are only divergent
if they meaningfully differ from the SOP, not just stylistic variations.
""",
)

_synopsis_agent: Agent[None, str] = Agent(
    _model,
    name="reviewer.synopsis",
    output_type=str,
    system_prompt="""\
You are writing an operator behavioural synopsis for a manufacturing AI assistant.
Write a single paragraph (4-6 sentences) in third person describing the operator's
observable patterns: preferred instruction style, confidence on alarm types,
escalation behaviour, troubleshooting approach, and any learning needs.
Base it only on the provided profile items and recent events — do not speculate.
Be concrete and specific. If the profile is sparse, say so and note what is known.
""",
)


# ── Public API ────────────────────────────────────────────────────────────────

async def consolidate(
    recent_events: list[dict],
    profile: OperatorProfile,
    operator_id: str,
    source_event_id: str,
) -> tuple[list, list[Hypothesis]]:
    """
    Returns (list[MemoryOperation], list[Hypothesis]) — pipeline persists them.
    """
    from ola.domain.memory import MemoryOperation

    items_text = "\n".join(
        f"  [{i.id[:8]}] [{i.status}, n={i.evidence_count}] ({i.category.value}) {i.text}"
        for i in profile.active_items
    ) or "  (none)"

    events_text = "\n".join(
        f"  [{e.get('role','?')}] {e.get('event_type','?')}: {e.get('content','')[:200]}"
        for e in recent_events[-20:]  # cap context
    )

    prompt = (
        f"Recent operator events (latest 20):\n{events_text}\n\n"
        f"Current active profile:\n{items_text}\n\n"
        "Propose memory operations and hypotheses based on the evidence above."
    )

    async with agent_span("reviewer.consolidate"):
        result = await _consolidate_agent.run(prompt)
    out = result.output

    now = datetime.now(timezone.utc)
    ops: list[MemoryOperation] = []
    for dec in out.memory_operations:
        op_type = dec.op_type.upper()
        if op_type not in {"ADD", "REINFORCE", "SUPERSEDE", "NOOP"}:
            continue
        cat = None
        if dec.category:
            try:
                cat = TraitCategory(dec.category)
            except ValueError:
                pass
        ops.append(
            MemoryOperation(
                id=str(uuid.uuid4()),
                operator_id=operator_id,
                op_type=op_type,  # type: ignore[arg-type]
                target_item_id=dec.target_item_id if op_type in {"REINFORCE", "SUPERSEDE"} else None,
                text=dec.text if op_type in {"ADD", "SUPERSEDE"} else None,
                value=dec.value if op_type in {"ADD", "SUPERSEDE"} else None,
                category=cat,
                source_event_id=source_event_id,
                rationale=dec.rationale,
                source="reviewer",
                timestamp=now,
            )
        )

    hypotheses: list[Hypothesis] = [
        Hypothesis(
            id=str(uuid.uuid4()),
            operator_id=operator_id,
            kind=h.kind,
            description=h.description,
            created_at=now,
        )
        for h in out.hypotheses
    ]

    return ops, hypotheses


async def classify_conformance(
    alarm_code: str,
    procedure_title: str,
    procedure_steps: list[str],
    observed_outcome: str,
    observed_text: str,
) -> ConformanceResult:
    prompt = (
        f"Alarm: {alarm_code}\n"
        f"SOP: {procedure_title}\n"
        f"Expected steps:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(procedure_steps)) + "\n\n"
        f"What the operator did:\n  {observed_text}\n"
        f"Outcome: {observed_outcome}"
    )
    async with agent_span("reviewer.conformance"):
        result = await _conformance_agent.run(prompt)
    return result.output


async def generate_synopsis(profile: OperatorProfile, recent_events: list[dict]) -> str:
    items_text = "\n".join(
        f"- [{i.status}, n={i.evidence_count}] ({i.category.value}) {i.text}"
        for i in profile.active_items
    ) or "(no profile items)"

    events_summary = "\n".join(
        f"  {e.get('event_type','?')}: {e.get('content','')[:150]}"
        for e in recent_events[-10:]
    )

    prompt = (
        f"Operator: {profile.operator_id}\n\n"
        f"Profile items:\n{items_text}\n\n"
        f"Recent interactions (sample):\n{events_summary}"
    )
    async with agent_span("reviewer.synopsis"):
        result = await _synopsis_agent.run(prompt)
    return result.output
