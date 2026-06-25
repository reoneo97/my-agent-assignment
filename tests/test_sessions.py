"""
Unit tests for session lifecycle orchestration (docs/sessions.md). No network
required — KG/LLM calls are mocked, mirroring tests/test_projection.py's style.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryOperation
from ola.domain.signals import TraitCategory
from ola.memory.store import (
    append_event,
    get_open_session_activity,
    get_profile,
    get_session,
    open_session,
)
from ola.sessions import close_if_timed_out, finalize_session_close, open_alarm_session


def _db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_operator_event(operator_id: str, session_id: str, db_path: str, content: str = "hi") -> str:
    event_id = str(uuid.uuid4())
    append_event(
        OperatorInteraction(
            id=event_id, operator_id=operator_id, session_id=session_id, role="operator",
            timestamp=_now(), event_type="question", content=content,
        ),
        db_path=db_path,
    )
    return event_id


async def test_close_if_timed_out_abandons_stale_session() -> None:
    db = _db()
    op_id = "op-1"
    session_id = open_session(op_id, trigger_alarm_code="PA-2201", db_path=db)
    # Backdate the only event so the session looks stale.
    stale_event = OperatorInteraction(
        id=str(uuid.uuid4()), operator_id=op_id, session_id=session_id, role="system",
        timestamp=_now() - timedelta(hours=1), event_type="alarm", content="Alarm fired.",
    )
    append_event(stale_event, db_path=db)

    with patch("ola.sessions.conformance_route") as mock_route:
        await close_if_timed_out(op_id, db_path=db)

    session = get_session(session_id, db_path=db)
    assert session is not None
    assert session["status"] == "abandoned"
    mock_route.assert_called_once()
    assert get_open_session_activity(op_id, db_path=db) is None


async def test_close_if_timed_out_leaves_active_session_open() -> None:
    db = _db()
    op_id = "op-1"
    session_id = open_session(op_id, db_path=db)
    _append_operator_event(op_id, session_id, db)

    await close_if_timed_out(op_id, db_path=db)

    session = get_session(session_id, db_path=db)
    assert session is not None
    assert session["status"] == "open"


async def test_open_alarm_session_supersedes_existing_open_session() -> None:
    db = _db()
    op_id = "op-demo-01"
    old_session_id = open_session(op_id, trigger_alarm_code="HY-0042", db_path=db)
    _append_operator_event(op_id, old_session_id, db)

    with (
        patch("ola.sessions.list_alarm_codes", return_value=[{"code": "PA-2201", "complexity": "low"}]),
        patch("ola.sessions.list_machines", return_value=["DA-L2-01"]),
        patch("ola.sessions.get_operator_alarm_disposition", return_value="confident"),
        patch("ola.sessions.conformance_route") as mock_route,
    ):
        result = await open_alarm_session(op_id, db_path=db)

    old_session = get_session(old_session_id, db_path=db)
    assert old_session is not None
    assert old_session["status"] == "abandoned"
    assert result["session_id"] != old_session_id
    assert result["alarm_code"] == "PA-2201"
    assert result["proactive_message"] is None  # "confident" => stay minimal
    assert mock_route.call_count == 1  # once for the superseded session's close


async def test_open_alarm_session_proactive_when_not_confident() -> None:
    db = _db()
    op_id = "op-demo-01"

    with (
        patch("ola.sessions.list_alarm_codes", return_value=[{"code": "HY-0042", "complexity": "high"}]),
        patch("ola.sessions.list_machines", return_value=["WB-PA-01"]),
        patch("ola.sessions.get_operator_alarm_disposition", return_value="struggles"),
        patch("ola.sessions.generate_response_from_bundle", new=AsyncMock(return_value="Let me help.")),
    ):
        result = await open_alarm_session(op_id, db_path=db)

    assert result["proactive_message"] == "Let me help."
    thread = get_session(result["session_id"], db_path=db)
    assert thread is not None and thread["trigger_alarm_code"] == "HY-0042"


def _add_op(op_id: str, src: str) -> MemoryOperation:
    return MemoryOperation(
        id=str(uuid.uuid4()), operator_id=op_id, op_type="ADD",
        text="Resolves independently without help", category=TraitCategory.ISSUE_CONFIDENCE,
        source_event_id=src, timestamp=_now(),
    )


@pytest.mark.parametrize("outcome", ["resolved_independently", "escalated"])
async def test_quiet_operator_signal_fires_on_good_outcome_without_engagement(outcome: str) -> None:
    db = _db()
    op_id = "op-1"
    session_id = open_session(op_id, trigger_alarm_code="PA-2201", db_path=db)
    # Only a system alarm event + the closing event itself — no operator engagement.
    append_event(
        OperatorInteraction(
            id=str(uuid.uuid4()), operator_id=op_id, session_id=session_id, role="system",
            timestamp=_now(), event_type="alarm", content="Alarm fired.",
        ),
        db_path=db,
    )
    closing_id = str(uuid.uuid4())
    append_event(
        OperatorInteraction(
            id=closing_id, operator_id=op_id, session_id=session_id, role="operator",
            timestamp=_now(), event_type="resolution_action", outcome=outcome, content="Marked resolved.",
        ),
        db_path=db,
    )

    with (
        patch("ola.sessions.conformance_route"),
        patch("ola.sessions.decide_operations", new=AsyncMock(return_value=[_add_op(op_id, closing_id)])),
    ):
        await finalize_session_close(session_id, op_id, closing_id, outcome, db_path=db)

    profile = get_profile(op_id, db_path=db)
    assert any(i.category == TraitCategory.ISSUE_CONFIDENCE for i in profile.active_items)


@pytest.mark.parametrize("outcome", ["unresolved", "abandoned"])
async def test_quiet_operator_signal_never_fires_on_bad_outcome(outcome: str) -> None:
    """§5/§7.5 negative case: never infer confidence from silence + a bad outcome."""
    db = _db()
    op_id = "op-1"
    session_id = open_session(op_id, trigger_alarm_code="PA-2201", db_path=db)
    closing_id = str(uuid.uuid4())
    append_event(
        OperatorInteraction(
            id=closing_id, operator_id=op_id, session_id=session_id, role="system",
            timestamp=_now(), event_type="session_timeout", content="Session closed.",
        ),
        db_path=db,
    )

    with (
        patch("ola.sessions.conformance_route"),
        patch("ola.sessions.decide_operations", new=AsyncMock()) as mock_decide,
    ):
        await finalize_session_close(session_id, op_id, closing_id, outcome, db_path=db)
        mock_decide.assert_not_called()

    profile = get_profile(op_id, db_path=db)
    assert profile.active_items == []


async def test_quiet_operator_signal_skipped_when_engaged() -> None:
    db = _db()
    op_id = "op-1"
    session_id = open_session(op_id, trigger_alarm_code="PA-2201", db_path=db)
    _append_operator_event(op_id, session_id, db, content="I need help with this.")
    closing_id = str(uuid.uuid4())
    append_event(
        OperatorInteraction(
            id=closing_id, operator_id=op_id, session_id=session_id, role="operator",
            timestamp=_now(), event_type="resolution_action",
            outcome="resolved_independently", content="Marked resolved.",
        ),
        db_path=db,
    )

    with (
        patch("ola.sessions.conformance_route"),
        patch("ola.sessions.decide_operations", new=AsyncMock()) as mock_decide,
    ):
        await finalize_session_close(session_id, op_id, closing_id, "resolved_independently", db_path=db)
        mock_decide.assert_not_called()
