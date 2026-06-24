"""
Context Assembler — deterministic, no LLM.
Builds the ContextBundle fed to the Responder from:
  - session thread (episodic working memory)
  - operator profile slice (relevant items only)
  - synopsis
  - KG neighborhood (procedure, disposition, modalities, skills, siblings)
"""

from __future__ import annotations

from pydantic import BaseModel

from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryItem, OperatorProfile
from ola.domain.signals import TraitCategory
from ola.kg.queries import get_alarm_context, get_operator_confidence_transfer
from ola.memory.store import get_session_thread, get_synopsis
from ola.personalization.render import derive_directive, render_profile


class ContextBundle(BaseModel):
    operator_message: str
    session_thread: list[dict]
    synopsis: str | None
    relevant_profile_items: list[dict]
    kg_context: dict
    personalization_directive: str
    validation_directive: str | None


def _select_relevant_items(
    profile: OperatorProfile,
    alarm_code: str | None,
    event_type: str,
) -> list[MemoryItem]:
    """Return the profile slice most relevant to the current situation."""
    active = profile.active_items

    # Always include modality, escalation, and any situation-specific items
    priority_cats = {TraitCategory.INSTRUCTION_MODALITY, TraitCategory.ESCALATION}
    if alarm_code:
        priority_cats.add(TraitCategory.ISSUE_CONFIDENCE)
    if event_type in ("alarm",):
        priority_cats.add(TraitCategory.TROUBLESHOOTING)

    return [i for i in active if i.category in priority_cats] or active[:5]


def assemble(
    interaction: OperatorInteraction,
    profile: OperatorProfile,
    validation_directive: str | None = None,
    db_path: str | None = None,
) -> ContextBundle:
    kwargs = {"db_path": db_path} if db_path else {}

    # 1. Session thread (working memory for this issue)
    thread: list[dict] = []
    if interaction.session_id:
        thread = get_session_thread(interaction.session_id, **kwargs)

    # 2. Synopsis
    synopsis_row = get_synopsis(interaction.operator_id, **kwargs)
    synopsis_text = synopsis_row["text"] if synopsis_row else None

    # 3. KG neighborhood
    kg_ctx: dict = {}
    if interaction.alarm_code:
        kg_ctx = get_alarm_context(interaction.alarm_code)
        # Confidence transfer from sibling
        transfer = get_operator_confidence_transfer(interaction.operator_id, interaction.alarm_code)
        if transfer is not None:
            kg_ctx["sibling_confidence_transfer"] = transfer

    # 4. Profile slice
    relevant = _select_relevant_items(profile, interaction.alarm_code, interaction.event_type)
    relevant_dicts = [
        {
            "text": item.text,
            "category": item.category.value,
            "status": item.status,
            "evidence_count": item.evidence_count,
        }
        for item in relevant
    ]

    # 5. Directives
    personalization = derive_directive(profile, situation=interaction.content)

    return ContextBundle(
        operator_message=interaction.content,
        session_thread=thread,
        synopsis=synopsis_text,
        relevant_profile_items=relevant_dicts,
        kg_context=kg_ctx,
        personalization_directive=personalization,
        validation_directive=validation_directive,
    )
