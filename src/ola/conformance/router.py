"""
Conformance Router — deterministic check. No LLM.

Called once at session-close time (not per operator turn) with the session's
trigger alarm code. Decides whether the alarm is SOP-evaluable (i.e., there is
a known procedure in the KG for it). If so, creates a PENDING conformance_event.
"""

from __future__ import annotations

import uuid

from ola.kg.queries import get_alarm_context
from ola.memory.store import append_conformance_event


def route(
    alarm_code: str | None,
    operator_id: str,
    source_event_id: str,
    db_path: str | None = None,
) -> str | None:
    """
    If evaluable, write a PENDING conformance_event and return its ID.
    Returns None if not evaluable (no alarm code, or alarm not in KG).
    """
    if not alarm_code:
        return None

    kg = get_alarm_context(alarm_code)
    if not kg or not kg.get("procedure_id"):
        return None

    conformance_id = str(uuid.uuid4())
    kwargs = {"db_path": db_path} if db_path else {}
    expected_disposition = kg.get("expected_disposition")
    append_conformance_event(
        event_id=conformance_id,
        source_event_id=source_event_id,
        operator_id=operator_id,
        alarm_code=alarm_code,
        procedure_id=kg["procedure_id"],
        # KG stores lowercase ('self_resolve'/'escalate'/'either'); the
        # conformance_events.expected_disposition CHECK expects uppercase.
        expected_disposition=expected_disposition.upper() if expected_disposition else None,
        **kwargs,
    )
    return conformance_id
