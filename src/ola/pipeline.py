from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ola.agents.extractor import extract_signals
from ola.agents.memory_manager import decide_operations
from ola.agents.responder import generate_response, stream_response
from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryOperation, OperatorProfile
from ola.memory.store import append_event, append_operation, get_profile
from ola.personalization.render import derive_directive, render_profile


async def process_interaction(
    interaction: OperatorInteraction,
    db_path: str | None = None,
) -> tuple[list[MemoryOperation], OperatorProfile, str]:
    """
    Core learning loop:
    ingest -> extract -> manage memory -> apply ops -> render -> respond

    Returns (applied_ops, updated_profile, response_text).
    This is the seam where Stage-2 KG projection will later hook in.
    """
    kwargs = {"db_path": db_path} if db_path else {}

    # 1. Ingest
    append_event(interaction, **kwargs)

    # 2. Extract behavioural signals
    signals = await extract_signals(interaction)

    # 3. Current profile (before this interaction's ops)
    profile_before = get_profile(interaction.operator_id, **kwargs)

    # 4. Memory manager decides operations
    ops = await decide_operations(
        signals=signals,
        current_items=profile_before.active_items,
        operator_id=interaction.operator_id,
        source_event_id=interaction.id,
    )

    # 5. Apply ops (append-only)
    for op in ops:
        append_operation(op, **kwargs)

    # 6. Derive updated profile by folding the log
    profile_after = get_profile(interaction.operator_id, **kwargs)

    # 7. Render profile + directive
    profile_block = render_profile(profile_after)
    directive = derive_directive(profile_after, situation=interaction.raw_text)

    # 8. Generate personalized response
    response = await generate_response(interaction, profile_block, directive)

    return ops, profile_after, response


async def stream_interaction(
    interaction: OperatorInteraction,
    db_path: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Streaming variant of process_interaction.
    Yields dicts with a 'type' discriminator:
      {"type": "ops",     "ops": [...]}
      {"type": "profile", "items": [...]}
      {"type": "chunk",   "text": "..."}
      {"type": "done"}
    """
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}  # type: ignore[assignment]

    append_event(interaction, **kwargs)
    signals = await extract_signals(interaction)
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
    profile_block = render_profile(profile_after)
    directive = derive_directive(profile_after, situation=interaction.raw_text)

    yield {
        "type": "ops",
        "ops": [
            {
                "op_type": op.op_type,
                "target_item_id": op.target_item_id,
                "text": op.text,
                "category": op.category.value if op.category else None,
            }
            for op in ops
        ],
    }

    yield {
        "type": "profile",
        "items": [
            {
                "id": item.id,
                "text": item.text,
                "category": item.category.value,
                "status": item.status,
                "evidence_count": item.evidence_count,
            }
            for item in profile_after.active_items
        ],
    }

    async for chunk in stream_response(interaction, profile_block, directive):
        yield {"type": "chunk", "text": chunk}

    yield {"type": "done"}
