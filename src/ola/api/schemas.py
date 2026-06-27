from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ── Shared profile shape (§5) ─────────────────────────────────────────────────

class ProfileItemOut(BaseModel):
    id: str
    text: str
    category: str
    status: str
    evidence_count: int
    source_event_ids: list[str]
    last_updated: datetime


class ProfileOut(BaseModel):
    operator_id: str
    items: list[ProfileItemOut]


# ── /api/interaction ──────────────────────────────────────────────────────────

class InteractionRequest(BaseModel):
    operator_id: str = "op-demo-01"
    session_id: str | None = None  # held by client after mock alarm; route falls back to get_or_create if absent
    source: Literal["user", "simulated"] = "user"
    message: str | None = None   # required when source="user" and outcome is not set
    outcome: Literal["resolved_independently", "escalated"] | None = None  # explicit Resolve/Escalate action


class SignalOut(BaseModel):
    category: str
    value: str
    observation: str


class MemoryOpOut(BaseModel):
    op_type: str
    target_item_id: str | None
    text: str | None
    category: str | None


class InteractionOut(BaseModel):
    id: str
    operator_message: str
    timestamp: datetime
    alarm_code: str | None
    shift: str | None


class InteractionResponse(BaseModel):
    interaction: InteractionOut
    assistant_reply: str
    validation_requested: bool = False
    signals_extracted: list[SignalOut]
    memory_operations: list[MemoryOpOut]
    profile: ProfileOut


# ── /api/shift/end ────────────────────────────────────────────────────────────

class ShiftEndRequest(BaseModel):
    operator_id: str = "op-demo-01"
    shift: str = "day"


class TierTransition(BaseModel):
    item_id: str
    from_status: str
    to_status: str


class SupersededRef(BaseModel):
    item_id: str
    by: str


class ShiftChanges(BaseModel):
    tier_transitions: list[TierTransition]
    new_items: list[ProfileItemOut]
    superseded: list[SupersededRef]


class ShiftEndResponse(BaseModel):
    no_significant_updates: bool
    changes: ShiftChanges
    profile_before: ProfileOut
    profile_after: ProfileOut
    synopsis_before: str
    synopsis_after: str


# ── /api/synopsis ─────────────────────────────────────────────────────────────

class SynopsisOut(BaseModel):
    text: str
    generated_at: datetime
    version: int


# ── /api/operators ────────────────────────────────────────────────────────────

class OperatorOut(BaseModel):
    id: str
    name: str
    machine_type: str


class OperatorsResponse(BaseModel):
    operators: list[OperatorOut]


# ── /api/alarm/mock ───────────────────────────────────────────────────────────

class MockAlarmRequest(BaseModel):
    operator_id: str = "op-demo-01"


class AlarmOut(BaseModel):
    code: str | None
    machine_id: str | None
    complexity: str | None = None
    severity: str | None = None
    expected_disposition: str | None = None


class MockAlarmResponse(BaseModel):
    session_id: str
    alarm: AlarmOut
    system_message: str
    proactive_reply: str | None = None


# ── /api/eval ─────────────────────────────────────────────────────────────────

class TraitMatch(BaseModel):
    trait: str
    category: str
    matched: bool
    inferred_text: str | None


class EvalResponse(BaseModel):
    operator_id: str
    matched: list[TraitMatch]
    missed: list[TraitMatch]
    spurious: list[str]
    score: float  # matched / (matched + missed + spurious)
