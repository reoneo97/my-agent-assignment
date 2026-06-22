from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.memory import MemoryItem, MemoryOperation
from ola.domain.signals import BehaviouralSignal

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


class OperationList(BaseModel):
    operations: list[OpDecision]


_agent: Agent[None, OperationList] = Agent(
    make_model(),
    output_type=OperationList,
    system_prompt=_SYSTEM,
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
    result = await _agent.run(prompt)

    ops: list[MemoryOperation] = []
    now = datetime.now(timezone.utc)
    for dec in result.output.operations:
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

        ops.append(
            MemoryOperation(
                id=str(uuid.uuid4()),
                operator_id=operator_id,
                op_type=op_type,  # type: ignore[arg-type]
                target_item_id=dec.target_item_id if op_type in {"REINFORCE", "SUPERSEDE"} else None,
                text=dec.text if op_type in {"ADD", "SUPERSEDE"} else None,
                category=category,
                source_event_id=source_event_id,
                timestamp=now,
            )
        )
    return ops
