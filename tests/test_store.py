"""Unit tests for append-only store + fold. No network required."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryOperation
from ola.domain.signals import TraitCategory
from ola.memory.store import (
    append_event,
    append_operation,
    get_or_create_session,
    get_profile,
    reset_operator,
)


def _db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _interaction(op_id: str, event_id: str | None = None) -> OperatorInteraction:
    return OperatorInteraction(
        id=event_id or str(uuid.uuid4()),
        operator_id=op_id,
        session_id="",
        timestamp=_now(),
        shift="day",
        event_type="alarm",
        alarm_code="PA-2201",
        content="High pressure alarm.",
        outcome="resolved_independently",
    )


def _with_session(interaction: OperatorInteraction, db_path: str) -> OperatorInteraction:
    sid = get_or_create_session(interaction.operator_id, db_path=db_path)
    return interaction.model_copy(update={"session_id": sid})


def _add_op(op_id: str, src: str, text: str, cat: TraitCategory) -> MemoryOperation:
    return MemoryOperation(
        id=str(uuid.uuid4()),
        operator_id=op_id,
        op_type="ADD",
        text=text,
        category=cat,
        source_event_id=src,
        timestamp=_now(),
    )


def _reinforce_op(op_id: str, target: str, src: str) -> MemoryOperation:
    return MemoryOperation(
        id=str(uuid.uuid4()),
        operator_id=op_id,
        op_type="REINFORCE",
        target_item_id=target,
        source_event_id=src,
        timestamp=_now(),
    )


def _supersede_op(op_id: str, target: str, src: str, text: str, cat: TraitCategory) -> MemoryOperation:
    return MemoryOperation(
        id=str(uuid.uuid4()),
        operator_id=op_id,
        op_type="SUPERSEDE",
        target_item_id=target,
        text=text,
        category=cat,
        source_event_id=src,
        timestamp=_now(),
    )


def test_empty_profile() -> None:
    db = _db()
    profile = get_profile("op-1", db_path=db)
    assert profile.active_items == []


def test_add_creates_tentative_item() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    add = _add_op(op_id, "evt-1", "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)

    profile = get_profile(op_id, db_path=db)
    assert len(profile.active_items) == 1
    item = profile.active_items[0]
    assert item.status == "tentative"
    assert item.evidence_count == 1
    assert item.text == "Prefers visual instructions"


def test_reinforce_raises_count_and_tier() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    add = _add_op(op_id, "evt-1", "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)
    item_id = add.id

    for i in range(2):
        src = f"evt-{i + 2}"
        i2 = _with_session(_interaction(op_id, src), db)
        append_event(i2, db_path=db)
        append_operation(_reinforce_op(op_id, item_id, src), db_path=db)

    profile = get_profile(op_id, db_path=db)
    assert len(profile.active_items) == 1
    item = profile.active_items[0]
    assert item.status == "established"
    assert item.evidence_count == 3


def test_supersede_removes_old_adds_new() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    add = _add_op(op_id, "evt-1", "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)

    i2 = _with_session(_interaction(op_id, "evt-2"), db)
    append_event(i2, db_path=db)
    sup = _supersede_op(op_id, add.id, "evt-2", "Prefers concise text steps now", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(sup, db_path=db)

    profile = get_profile(op_id, db_path=db)
    texts = [i.text for i in profile.active_items]
    assert "Prefers concise text steps now" in texts
    assert "Prefers visual instructions" not in texts


def test_fold_is_deterministic_replay() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    add = _add_op(op_id, "evt-1", "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)

    i2 = _with_session(_interaction(op_id, "evt-2"), db)
    append_event(i2, db_path=db)
    append_operation(_reinforce_op(op_id, add.id, "evt-2"), db_path=db)

    assert get_profile(op_id, db_path=db).model_dump() == get_profile(op_id, db_path=db).model_dump()


def test_provenance_tracked() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    add = _add_op(op_id, "evt-1", "Escalates complex faults", TraitCategory.ESCALATION)
    append_operation(add, db_path=db)

    i2 = _with_session(_interaction(op_id, "evt-2"), db)
    append_event(i2, db_path=db)
    append_operation(_reinforce_op(op_id, add.id, "evt-2"), db_path=db)

    item = get_profile(op_id, db_path=db).active_items[0]
    assert "evt-1" in item.source_event_ids
    assert "evt-2" in item.source_event_ids


def test_high_weight_promotes_to_confirmed() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    add = _add_op(op_id, "evt-1", "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)

    hw_op = MemoryOperation(
        id=str(uuid.uuid4()),
        operator_id=op_id,
        op_type="REINFORCE",
        target_item_id=add.id,
        source_event_id="evt-2",
        high_weight=True,
        timestamp=_now(),
    )
    i2 = _with_session(_interaction(op_id, "evt-2"), db)
    append_event(i2, db_path=db)
    append_operation(hw_op, db_path=db)

    item = get_profile(op_id, db_path=db).active_items[0]
    assert item.status == "confirmed"


def test_reset_clears_operator() -> None:
    db = _db()
    op_id = "op-1"
    i1 = _with_session(_interaction(op_id, "evt-1"), db)
    append_event(i1, db_path=db)
    append_operation(_add_op(op_id, "evt-1", "Some belief", TraitCategory.ESCALATION), db_path=db)

    reset_operator(op_id, db_path=db)
    assert get_profile(op_id, db_path=db).active_items == []
