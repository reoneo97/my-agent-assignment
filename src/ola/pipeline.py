"""
Pipeline — hot path entrypoint. Deterministic orchestration; no routing LLM.

Flow (§6.2 of PRD v2):
  1. Session management (open or continue)
  2. Append operator event
  3. Extractor → signals → persist
  4. Memory Manager → operations → persist
  5. Tier recompute → Projection for newly-established items
  6. Conformance Router → PENDING conformance_event if SOP exists
  7. Context Assembler → ContextBundle
  8. Validation Gate → validation_directive
  9. Responder → reply
  10. Append assistant event
  11. Session close if outcome set
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from ola.agents.extractor import extract_signals
from ola.agents.memory_manager import decide_operations
from ola.agents.responder import generate_response, generate_response_from_bundle, stream_response
from ola.conformance.router import route as conformance_route
from ola.context_assembler import assemble
from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryOperation, OperatorProfile
from ola.domain.signals import BehaviouralSignal
from ola.kg.projection import project_profile
from ola.memory.store import (
    append_event,
    append_operation,
    append_signal,
    close_session,
    get_or_create_session,
    get_profile,
)
from ola.personalization.render import derive_directive, render_profile
from ola.personalization.validation_gate import decide as validation_gate_decide


async def process_interaction(
    interaction: OperatorInteraction,
    db_path: str | None = None,
) -> tuple[list[BehaviouralSignal], list[MemoryOperation], OperatorProfile, str]:
    """
    Returns (signals, ops, updated_profile, reply).
    This is the Stage-2 KG projection seam.
    """
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}  # type: ignore[assignment]

    # 1. Session
    session_id = get_or_create_session(
        interaction.operator_id,
        trigger_alarm_code=interaction.alarm_code,
        machine_id=interaction.machine_id,
        **kwargs,
    )
    interaction = interaction.model_copy(update={"session_id": session_id, "role": "operator"})

    # 2. Append operator event
    append_event(interaction, **kwargs)

    # 3. Extract signals
    signals = await extract_signals(interaction)
    now = datetime.now(timezone.utc)
    for sig in signals:
        append_signal(
            signal_id=str(uuid.uuid4()),
            source_event_id=sig.source_event_id,
            operator_id=interaction.operator_id,
            category=sig.category.value,
            value=sig.value,
            observation=sig.observation,
            timestamp=now,
            **kwargs,
        )

    # 4. Memory Manager
    profile_before = get_profile(interaction.operator_id, **kwargs)
    ops = await decide_operations(
        signals=signals,
        current_items=profile_before.active_items,
        operator_id=interaction.operator_id,
        source_event_id=interaction.id,
    )
    # Tag as high_weight if this is a confirmation response
    if interaction.event_type == "confirmation_response":
        for op in ops:
            op.high_weight = True
    for op in ops:
        append_operation(op, **kwargs)

    # 5. Tier recompute + Projection
    profile_after = get_profile(interaction.operator_id, **kwargs)
    project_profile(profile_after, profile_before)

    # 6. Conformance Router
    conformance_route(interaction, db_path=db_path)

    # 7. Context Assembler
    vg_directive = validation_gate_decide(profile_after, ops, interaction.event_type)
    bundle = assemble(interaction, profile_after, validation_directive=vg_directive, db_path=db_path)

    # 8. Responder
    reply = await generate_response_from_bundle(bundle)

    # 9. Append assistant event
    assistant_event = OperatorInteraction(
        id=str(uuid.uuid4()),
        operator_id=interaction.operator_id,
        session_id=session_id,
        role="assistant",
        timestamp=datetime.now(timezone.utc),
        event_type="reply",
        content=reply,
    )
    append_event(assistant_event, **kwargs)

    # 10. Session close
    if interaction.outcome in ("resolved_independently", "escalated", "unresolved"):
        status = "resolved" if interaction.outcome == "resolved_independently" else (
            "escalated" if interaction.outcome == "escalated" else "resolved"
        )
        close_session(session_id, status, **kwargs)

    return signals, ops, profile_after, reply


async def stream_interaction(
    interaction: OperatorInteraction,
    db_path: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Streaming variant for the legacy SSE endpoint.
    Yields: signals → ops → profile → system_prompt → chunk... → done
    """
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}  # type: ignore[assignment]

    session_id = get_or_create_session(
        interaction.operator_id,
        trigger_alarm_code=interaction.alarm_code,
        machine_id=interaction.machine_id,
        **kwargs,
    )
    interaction = interaction.model_copy(update={"session_id": session_id, "role": "operator"})
    append_event(interaction, **kwargs)

    signals = await extract_signals(interaction)
    now = datetime.now(timezone.utc)
    for sig in signals:
        append_signal(
            signal_id=str(uuid.uuid4()),
            source_event_id=sig.source_event_id,
            operator_id=interaction.operator_id,
            category=sig.category.value,
            value=sig.value,
            observation=sig.observation,
            timestamp=now,
            **kwargs,
        )

    profile_before = get_profile(interaction.operator_id, **kwargs)
    ops = await decide_operations(
        signals=signals,
        current_items=profile_before.active_items,
        operator_id=interaction.operator_id,
        source_event_id=interaction.id,
    )
    for op in ops:
        append_operation(op, **kwargs)

    profile_after = get_profile(interaction.operator_id, **kwargs)
    project_profile(profile_after, profile_before)
    conformance_route(interaction, db_path=db_path)

    profile_block = render_profile(profile_after)
    directive = derive_directive(profile_after, situation=interaction.content)

    yield {"type": "signals", "signals": [{"category": s.category.value, "value": s.value, "observation": s.observation} for s in signals]}
    yield {"type": "ops", "ops": [{"op_type": op.op_type, "target_item_id": op.target_item_id, "text": op.text, "category": op.category.value if op.category else None} for op in ops]}
    yield {"type": "profile", "items": [{"id": i.id, "text": i.text, "category": i.category.value, "status": i.status, "evidence_count": i.evidence_count} for i in profile_after.active_items]}
    yield {"type": "system_prompt", "profile_block": profile_block, "directive": directive}

    full_reply = []
    async for chunk in stream_response(interaction.content, profile_block, directive):
        yield {"type": "chunk", "text": chunk}
        full_reply.append(chunk)

    assistant_event = OperatorInteraction(
        id=str(uuid.uuid4()),
        operator_id=interaction.operator_id,
        session_id=session_id,
        role="assistant",
        timestamp=datetime.now(timezone.utc),
        event_type="reply",
        content="".join(full_reply),
    )
    append_event(assistant_event, **kwargs)

    yield {"type": "done"}
