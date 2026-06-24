"""
Validation Gate — deterministic restraint policy. No LLM.

Ask for confirmation only when:
  (a) a tentative item is about to reduce scaffolding/support for the operator, OR
  (b) there is an active contradiction (an item was SUPERSEDE-d this turn).

Never ask on every turn; never add friction to escalation.
Returns a short validation_directive string or None.
"""

from __future__ import annotations

from ola.domain.memory import MemoryItem, MemoryOperation, OperatorProfile
from ola.domain.signals import TraitCategory


_SUPPORT_REDUCING_CATS = {
    TraitCategory.INSTRUCTION_MODALITY,
    TraitCategory.ISSUE_CONFIDENCE,
    TraitCategory.ESCALATION,
}


def decide(
    profile: OperatorProfile,
    ops: list[MemoryOperation],
    event_type: str,
) -> str | None:
    """
    Returns a validation_directive if a confirmation question should be woven
    into the Responder's reply, or None to stay silent.
    """
    # Case (b): contradiction — a SUPERSEDE was applied this turn
    superseded_this_turn = [op for op in ops if op.op_type == "SUPERSEDE"]
    if superseded_this_turn:
        cat_name = (
            superseded_this_turn[0].category.value
            if superseded_this_turn[0].category
            else "behaviour"
        )
        return (
            f"You noticed a potential change in the operator's {cat_name.lower().replace('_', ' ')}. "
            "Ask a brief, natural question to confirm the new pattern before acting on it."
        )

    # Case (a): tentative item that would reduce support
    tentative_support_reducing = [
        item for item in profile.active_items
        if item.status == "tentative" and item.category in _SUPPORT_REDUCING_CATS
    ]
    if tentative_support_reducing and event_type in ("alarm", "question"):
        item = tentative_support_reducing[0]
        return (
            f"You have a tentative belief: '{item.text}'. "
            "If it becomes relevant, weave in a brief, natural question to confirm it "
            "rather than assuming it. Do not ask multiple confirmation questions at once."
        )

    return None
