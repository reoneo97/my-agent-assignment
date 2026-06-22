from __future__ import annotations

from ola.domain.memory import MemoryItem, OperatorProfile
from ola.domain.signals import TraitCategory


def render_profile(profile: OperatorProfile) -> str:
    """Produce a tagged prompt block from active memory items."""
    if not profile.active_items:
        return "(No operator profile established yet — treat as new operator.)"

    lines: list[str] = []
    for item in profile.active_items:
        caution = ""
        if item.status == "tentative":
            caution = "  ← limited evidence, confirm if relevant"
        lines.append(f"- [{item.status}] {item.text}{caution}")

    return "\n".join(lines)


def derive_directive(profile: OperatorProfile, situation: str = "") -> str:
    """
    Code-derived instruction for the responder. Confidence-gated and asymmetric
    toward support: only reduce scaffolding for established/confirmed items.
    """
    active = profile.active_items
    if not active:
        return (
            "No profile yet. Provide full scaffolding, step-by-step instructions, "
            "and explicitly ask the operator to confirm any assumptions."
        )

    established = {item.category for item in active if item.status in ("established", "confirmed")}
    tentative = {item.category for item in active if item.status == "tentative"}

    parts: list[str] = []

    # Instruction modality
    if TraitCategory.INSTRUCTION_MODALITY in established:
        modality_items = [
            i for i in active
            if i.category == TraitCategory.INSTRUCTION_MODALITY
            and i.status in ("established", "confirmed")
        ]
        if modality_items:
            parts.append(f"Instruction style (confirmed): {modality_items[-1].text}")
    elif TraitCategory.INSTRUCTION_MODALITY in tentative:
        parts.append(
            "Instruction style is tentative — default to numbered, step-by-step format "
            "and confirm preferred style with the operator."
        )
    else:
        parts.append("Use numbered, step-by-step instructions (no style preference known).")

    # Escalation posture
    if TraitCategory.ESCALATION in established:
        esc_items = [
            i for i in active
            if i.category == TraitCategory.ESCALATION
            and i.status in ("established", "confirmed")
        ]
        if esc_items:
            parts.append(f"Escalation pattern (confirmed): {esc_items[-1].text}")
    else:
        parts.append("Escalation pattern unknown — offer escalation path explicitly.")

    # Issue confidence
    if TraitCategory.ISSUE_CONFIDENCE in tentative:
        parts.append(
            "Operator confidence on this issue type is uncertain — provide extra context and check understanding."
        )

    # Learning needs
    if TraitCategory.LEARNING_NEED in active:
        ln_items = [i for i in active if i.category == TraitCategory.LEARNING_NEED]
        for ln in ln_items:
            if ln.status == "tentative":
                parts.append(f"Possible learning need (unconfirmed): {ln.text} — mention gently.")
            else:
                parts.append(f"Known learning need: {ln.text} — address proactively.")

    # Verbosity: reduce only for well-established profile
    established_count = len(established)
    if established_count >= 3:
        parts.append("Profile is well-established — be concise; omit preamble.")
    else:
        parts.append("Profile is sparse — err toward fuller explanation and ask confirmatory questions.")

    return "\n".join(f"- {p}" for p in parts)
