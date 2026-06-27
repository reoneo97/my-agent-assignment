from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.memory import MemoryItem, MemoryOperation
from ola.domain.signals import BehaviouralSignal
from ola.telemetry import agent_span, log_agent_failure

_SYSTEM = """\
You are a memory manager for a manufacturing operator learning assistant.
Given new behavioural signals and the operator's current memory items,
decide what memory operations to apply.

For each signal, choose one operation:
- ADD: the belief is not yet captured — create a new memory item.
- REINFORCE: the signal confirms an existing item — reference its id.
- SUPERSEDE: the signal contradicts an existing item — mark old superseded, create replacement.
- NOOP: the signal is not salient or already covered.

Rules:
- Only ADD/SUPERSEDE include text (the belief statement).
- Only REINFORCE/SUPERSEDE include target_item_id.
- NOOP items have no text or target.
- Prefer REINFORCE over ADD when the existing belief is essentially the same.
- Prefer SUPERSEDE (not ADD) when contradicting an existing item.
- Keep belief text short (one sentence, NL).
"""


class OpDecision(BaseModel):
    op_type: str  # ADD | REINFORCE | SUPERSEDE | NOOP
    target_item_id: str | None = None
    text: str | None = None
    category: str | None = None  # TraitCategory value
    rationale: str = ""  # brief, for auditability


class OperationList(BaseModel):
    operations: list[OpDecision]


_agent: Agent[None, OperationList] = Agent(
    make_model(),
    output_type=OperationList,
    system_prompt=_SYSTEM,
    output_retries=3,
)


async def decide_operations(
    signals: list[BehaviouralSignal],
    current_items: list[MemoryItem],
    operator_id: str,
    source_event_id: str,
) -> list[MemoryOperation]:
    if not signals:
        return []

    items_text = "\n".join(
        f'  [{item.id}] ({item.category.value}, {item.status}, count={item.evidence_count}) "{item.text}"'
        for item in current_items
    ) or "  (none)"

    signals_text = "\n".join(
        f'  category={s.category.value} value="{s.value}" obs="{s.observation}"'
        for s in signals
    )

    prompt = f"""\
New signals from event {source_event_id}:
{signals_text}

Current active memory items:
{items_text}

Return one operation per signal (ADD/REINFORCE/SUPERSEDE/NOOP).
"""
    try:
        async with agent_span("memory_manager"):
            result = await _agent.run(prompt)
        decisions = result.output.operations
    except Exception as exc:
        log_agent_failure(
            agent_name="memory_manager",
            exc=exc,
            context={
                "operator_id": operator_id,
                "source_event_id": source_event_id,
                "signal_count": len(signals),
                "active_item_count": len(current_items),
            },
            prompt=prompt,
        )
        # Safe fallback: one NOOP per signal so the pipeline continues unmodified.
        now = datetime.now(timezone.utc)
        return [
            MemoryOperation(
                id=str(uuid.uuid4()),
                operator_id=operator_id,
                op_type="NOOP",
                source_event_id=source_event_id,
                rationale="memory_manager structured-output failure — graceful fallback",
                source="hot_path",
                timestamp=now,
            )
            for _ in signals
        ]

    ops: list[MemoryOperation] = []
    now = datetime.now(timezone.utc)
    for i, dec in enumerate(decisions):
        op_type = dec.op_type.upper()
        if op_type not in {"ADD", "REINFORCE", "SUPERSEDE", "NOOP"}:
            op_type = "NOOP"

        from ola.domain.signals import TraitCategory

        category = None
        if dec.category:
            try:
                category = TraitCategory(dec.category)
            except ValueError:
                category = None

        # Carry the normalized value from the corresponding signal (by index).
        signal_value = signals[i].value if i < len(signals) else None

        ops.append(
            MemoryOperation(
                id=str(uuid.uuid4()),
                operator_id=operator_id,
                op_type=op_type,  # type: ignore[arg-type]
                target_item_id=dec.target_item_id if op_type in {"REINFORCE", "SUPERSEDE"} else None,
                text=dec.text if op_type in {"ADD", "SUPERSEDE"} else None,
                value=signal_value if op_type in {"ADD", "SUPERSEDE"} else None,
                category=category,
                source_event_id=source_event_id,
                rationale=dec.rationale,
                source="hot_path",
                timestamp=now,
            )
        )
    return ops
