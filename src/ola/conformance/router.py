"""
Conformance Router — deterministic check. No LLM.

Decides whether an operator event is SOP-evaluable (i.e., there is a known
procedure in the KG for this alarm). If so, creates a PENDING conformance_event.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ola.domain.events import OperatorInteraction
from ola.kg.queries import get_alarm_context
from ola.memory.store import append_conformance_event


def route(interaction: OperatorInteraction, db_path: str | None = None) -> str | None:
    """
    If evaluable, write a PENDING conformance_event and return its ID.
    Returns None if not evaluable (no alarm code, or alarm not in KG).
    """
    if not interaction.alarm_code:
        return None

    kg = get_alarm_context(interaction.alarm_code)
    if not kg or not kg.get("procedure_id"):
        return None

    conformance_id = str(uuid.uuid4())
    kwargs = {"db_path": db_path} if db_path else {}
    append_conformance_event(
        event_id=conformance_id,
        source_event_id=interaction.id,
        operator_id=interaction.operator_id,
        alarm_code=interaction.alarm_code,
        procedure_id=kg["procedure_id"],
        expected_disposition=kg.get("expected_disposition"),
        **kwargs,
    )
    return conformance_id
