"""
Session lifecycle orchestration (docs/sessions.md).

Deterministic — code rules only, except the one optional proactive Responder
call in open_alarm_session(). No agent here mutates SQL/KG directly except via
the existing store/projection helpers.

Closure (soft, immediate) vs outcome verification (hard, deferred) are
deliberately decoupled: finalize_session_close() only stamps a *provisional*
outcome and reacts to it locally (conformance routing, quiet-operator signal).
The *verified* outcome is filled in later by conformance.outcome_resolver
during run_consolidation().
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
import mlflow

from ola.agents.memory_manager import decide_operations
from ola.agents.responder import generate_response_from_bundle
from ola.config import SESSION_INACTIVITY_TIMEOUT_MINUTES
from ola.conformance.router import route as conformance_route
from ola.context_assembler import assemble
from ola.domain.events import OperatorInteraction
from ola.domain.signals import BehaviouralSignal, TraitCategory
from ola.kg.projection import project_profile
from ola.kg.queries import get_operator_alarm_disposition, list_alarm_codes, list_machines
from ola.memory.store import (
    append_event,
    append_operation,
    close_session,
    get_open_session_activity,
    get_profile,
    get_session,
    get_session_thread,
    open_session,
)

_GOOD_OUTCOMES = ("resolved_independently", "escalated")


def _status_from_outcome(outcome: str) -> Literal["resolved", "escalated", "abandoned"]:
    if outcome == "escalated":
        return "escalated"
    if outcome == "abandoned":
        return "abandoned"
    return "resolved"  # resolved_independently | unresolved — closure bookkeeping only


async def finalize_session_close(
    session_id: str,
    operator_id: str,
    closing_event_id: str,
    provisional_outcome: str,
    db_path: str | None = None,
) -> None:
    """
    Runs whenever a session closes, regardless of trigger (explicit operator
    action, new-alarm supersede, or inactivity timeout). Caller must have
    already appended whatever event represents the closure trigger.
    """
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}

    close_session(session_id, status=_status_from_outcome(provisional_outcome), **kwargs)

    session = get_session(session_id, **kwargs)
    trigger_alarm_code = session.get("trigger_alarm_code") if session else None

    # Conformance-on-close (docs/sessions.md §6) — once per session, keyed to
    # the session's trigger alarm, not whatever the closing turn happened to carry.
    if trigger_alarm_code:
        conformance_route(trigger_alarm_code, operator_id, closing_event_id, db_path=db_path)

    # Quiet-operator signal (§5) — only infer confidence from silence + GOOD outcome.
    thread = get_session_thread(session_id, **kwargs)
    engaged = any(e["role"] == "operator" and e["id"] != closing_event_id for e in thread)
    if not engaged and provisional_outcome in _GOOD_OUTCOMES:
        signal = BehaviouralSignal(
            category=TraitCategory.ISSUE_CONFIDENCE,
            value="HIGH_CONFIDENCE_SILENT",
            observation=f"Resolved ({provisional_outcome}) without engaging the assistant"
            + (f" — alarm {trigger_alarm_code}" if trigger_alarm_code else ""),
            source_event_id=closing_event_id,
        )
        profile_before = get_profile(operator_id, **kwargs)
        ops = await decide_operations(
            signals=[signal],
            current_items=profile_before.active_items,
            operator_id=operator_id,
            source_event_id=closing_event_id,
        )
        for op in ops:
            append_operation(op, **kwargs)
        if ops:
            profile_after = get_profile(operator_id, **kwargs)
            project_profile(profile_after, profile_before)


async def close_if_timed_out(operator_id: str, db_path: str | None = None) -> None:
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}
    activity = get_open_session_activity(operator_id, **kwargs)
    if not activity:
        return

    last_activity = datetime.fromisoformat(activity["last_activity"])
    elapsed_minutes = (datetime.now(timezone.utc) - last_activity).total_seconds() / 60
    if elapsed_minutes < SESSION_INACTIVITY_TIMEOUT_MINUTES:
        return

    await _abandon_open_session(
        operator_id, activity["id"], event_type="session_timeout",
        content=f"Session closed — inactive for {int(elapsed_minutes)} minutes.",
        db_path=db_path,
    )


async def _abandon_open_session(
    operator_id: str,
    session_id: str,
    event_type: str,
    content: str,
    db_path: str | None = None,
) -> None:
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}
    closure_event = OperatorInteraction(
        id=str(uuid.uuid4()),
        operator_id=operator_id,
        session_id=session_id,
        role="system",
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        content=content,
    )
    append_event(closure_event, **kwargs)
    await finalize_session_close(
        session_id, operator_id, closing_event_id=closure_event.id,
        provisional_outcome="abandoned", db_path=db_path,
    )


def _sample_alarm_code(machine_type: str | None) -> dict[str, Any]:
    alarms = list_alarm_codes(machine_type)
    if not alarms:
        alarms = list_alarm_codes(None)
    if not alarms:
        return {"code": None}
    # Weight toward a mix: lower complexity = higher weight, so easy alarms aren't rare.
    weights = {"low": 3, "medium": 2, "high": 1}
    w = [weights.get((a.get("complexity") or "medium"), 2) for a in alarms]
    return random.choices(alarms, weights=w, k=1)[0]


async def open_alarm_session(
    operator_id: str,
    alarm_code: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, str] = {"db_path": db_path} if db_path else {}

    # 1. A new alarm supersedes any open session.
    activity = get_open_session_activity(operator_id, **kwargs)
    if activity:
        await _abandon_open_session(
            operator_id, activity["id"], event_type="session_superseded",
            content="Session abandoned — superseded by a new alarm.",
            db_path=db_path,
        )

    from sim.persona import get_machine_type

    machine_type = get_machine_type(operator_id)

    # 2. Sample alarm + 3. machine.
    alarm: dict[str, Any]
    if alarm_code:
        alarm = {"code": alarm_code}
    else:
        alarm = _sample_alarm_code(machine_type)
        alarm_code = alarm.get("code")

    machines = list_machines(machine_type) if machine_type else []
    machine_id = random.choice(machines) if machines else None

    # 4. Open session + system alarm event.
    session_id = open_session(
        operator_id, trigger_alarm_code=alarm_code, machine_id=machine_id, **kwargs
    )
    alarm_event = OperatorInteraction(
        id=str(uuid.uuid4()),
        operator_id=operator_id,
        session_id=session_id,
        role="system",
        timestamp=datetime.now(timezone.utc),
        event_type="alarm",
        alarm_code=alarm_code,
        machine_id=machine_id,
        content=f"Alarm {alarm_code} fired on {machine_id or 'an unspecified machine'}.",
    )
    append_event(alarm_event, **kwargs)
    print('Session ID:', session_id)

    with mlflow.tracing.context(session_id=session_id, user=operator_id):
        proactive_message: str | None = None
        if alarm_code:
            disposition = get_operator_alarm_disposition(operator_id, alarm_code)
            if disposition != "confident":
                profile = get_profile(operator_id, **kwargs)
                bundle = assemble(alarm_event, profile, db_path=db_path)
                proactive_message = await generate_response_from_bundle(bundle)
                assistant_event = OperatorInteraction(
                    id=str(uuid.uuid4()),
                    operator_id=operator_id,
                    session_id=session_id,
                    role="assistant",
                    timestamp=datetime.now(timezone.utc),
                    event_type="reply",
                    content=proactive_message,
                )
                append_event(assistant_event, **kwargs)

    return {
        "session_id": session_id,
        "alarm_code": alarm_code,
        "machine_id": machine_id,
        "kg_context": {k: v for k, v in alarm.items() if k != "code"},
        "proactive_message": proactive_message,
    }
