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
from ola.memory.store import append_event, append_operation, get_profile


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
        timestamp=_now(),
        shift="day",
        event_type="alarm",
        alarm_code="PA-2201",
        raw_text="High pressure alarm.",
        outcome="resolved_independently",
    )


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


def test_empty_profile():
    db = _db()
    profile = get_profile("op-1", db_path=db)
    assert profile.active_items == []


def test_add_creates_tentative_item():
    db = _db()
    op_id = "op-1"
    src = "evt-1"
    append_event(_interaction(op_id, src), db_path=db)
    add = _add_op(op_id, src, "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)

    profile = get_profile(op_id, db_path=db)
    assert len(profile.active_items) == 1
    item = profile.active_items[0]
    assert item.status == "tentative"
    assert item.evidence_count == 1
    assert item.text == "Prefers visual instructions"


def test_reinforce_raises_count_and_tier():
    db = _db()
    op_id = "op-1"
    src1 = "evt-1"
    append_event(_interaction(op_id, src1), db_path=db)
    add = _add_op(op_id, src1, "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)
    item_id = add.id

    # Two reinforcements -> count = 3 -> established
    for i in range(2):
        src = f"evt-{i + 2}"
        append_event(_interaction(op_id, src), db_path=db)
        append_operation(_reinforce_op(op_id, item_id, src), db_path=db)

    profile = get_profile(op_id, db_path=db)
    assert len(profile.active_items) == 1
    item = profile.active_items[0]
    assert item.status == "established"
    assert item.evidence_count == 3


def test_supersede_removes_old_adds_new():
    db = _db()
    op_id = "op-1"
    src1 = "evt-1"
    append_event(_interaction(op_id, src1), db_path=db)
    add = _add_op(op_id, src1, "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)
    old_id = add.id

    src2 = "evt-2"
    append_event(_interaction(op_id, src2), db_path=db)
    sup = _supersede_op(
        op_id, old_id, src2,
        "Prefers concise text steps now",
        TraitCategory.INSTRUCTION_MODALITY,
    )
    append_operation(sup, db_path=db)

    profile = get_profile(op_id, db_path=db)
    active_texts = [i.text for i in profile.active_items]
    assert "Prefers concise text steps now" in active_texts
    assert "Prefers visual instructions" not in active_texts


def test_fold_is_deterministic_replay():
    """Profile rebuilt from the same log must equal the original."""
    db = _db()
    op_id = "op-1"

    src1 = "evt-1"
    append_event(_interaction(op_id, src1), db_path=db)
    add = _add_op(op_id, src1, "Prefers visual instructions", TraitCategory.INSTRUCTION_MODALITY)
    append_operation(add, db_path=db)

    src2 = "evt-2"
    append_event(_interaction(op_id, src2), db_path=db)
    append_operation(_reinforce_op(op_id, add.id, src2), db_path=db)

    profile1 = get_profile(op_id, db_path=db)
    profile2 = get_profile(op_id, db_path=db)

    assert profile1.model_dump() == profile2.model_dump()


def test_provenance_tracked():
    db = _db()
    op_id = "op-1"
    src1, src2 = "evt-1", "evt-2"
    append_event(_interaction(op_id, src1), db_path=db)
    add = _add_op(op_id, src1, "Escalates complex faults", TraitCategory.ESCALATION)
    append_operation(add, db_path=db)

    append_event(_interaction(op_id, src2), db_path=db)
    append_operation(_reinforce_op(op_id, add.id, src2), db_path=db)

    profile = get_profile(op_id, db_path=db)
    item = profile.active_items[0]
    assert src1 in item.source_event_ids
    assert src2 in item.source_event_ids
