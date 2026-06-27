"""
Pipeline — hot path entrypoint. Deterministic orchestration; no routing LLM.

Flow (§6.2 of PRD v2; session semantics per docs/sessions.md):
  1. Session management (close if timed out; open or continue; backfill alarm/machine from session)
  2. Append operator event
  3. Extractor → signals → persist
  4. Memory Manager → operations → persist
  5. Tier recompute → Projection for newly-established items
  6. (Conformance Router runs at step 10, on close, not here)
  7. Context Assembler → ContextBundle
  8. Validation Gate → validation_directive
  9. Responder → reply
  10. Append assistant event
  11. Session close if outcome set → finalize_session_close() (conformance + quiet-signal)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ola.agents.extractor import extract_signals
from ola.agents.memory_manager import decide_operations
from ola.agents.responder import generate_response_from_bundle
from ola.context_assembler import assemble
from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryOperation, OperatorProfile
from ola.domain.signals import BehaviouralSignal
from ola.kg.projection import project_profile
from ola.memory.store import (
    append_event,
    append_operation,
    append_signal,
    get_profile,
    get_session,
)
from ola.personalization.validation_gate import decide as validation_gate_decide
from ola.sessions import finalize_session_close


async def process_interaction(
    interaction: OperatorInteraction,
    session_id: str,
    db_path: str | None = None,
) -> tuple[list[BehaviouralSignal], list[MemoryOperation], OperatorProfile, str]:
    """
    Returns (signals, ops, updated_profile, reply).
    session_id is resolved by the caller (route layer) — pipeline only processes the turn.
    """
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}  # type: ignore[assignment]

    # 1. Backfill alarm_code / machine_id from session when not on the interaction
    session_row = get_session(session_id, **kwargs)
    update: dict[str, Any] = {"session_id": session_id, "role": "operator"}
    if interaction.alarm_code is None and session_row and session_row.get("trigger_alarm_code"):
        update["alarm_code"] = session_row["trigger_alarm_code"]
    if interaction.machine_id is None and session_row and session_row.get("machine_id"):
        update["machine_id"] = session_row["machine_id"]
    interaction = interaction.model_copy(update=update)

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

    # 6. Conformance Router — runs at session close (step 10), keyed to the
    # session's trigger alarm, not every turn. See docs/sessions.md §6.

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

    # 10. Session close (provisional outcome — verified later by the Outcome Resolver)
    if interaction.outcome in ("resolved_independently", "escalated", "unresolved", "abandoned"):
        await finalize_session_close(
            session_id, interaction.operator_id,
            closing_event_id=interaction.id,
            provisional_outcome=interaction.outcome,
            db_path=db_path,
        )

    return signals, ops, profile_after, reply
