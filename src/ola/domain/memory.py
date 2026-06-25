from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ola.domain.signals import TraitCategory


class MemoryOperation(BaseModel):
    id: str
    operator_id: str
    op_type: Literal["ADD", "REINFORCE", "SUPERSEDE", "NOOP"]
    target_item_id: str | None = None
    text: str | None = None             # free-text belief content (human-facing)
    value: str | None = None            # normalized value from signal e.g. 'VISUAL' (machine-facing)
    category: TraitCategory | None = None
    source_event_id: str
    rationale: str = ""                 # brief, for auditability (not persisted to DB)
    source: Literal["hot_path", "reviewer"] = "hot_path"
    high_weight: bool = False
    timestamp: datetime


class MemoryItem(BaseModel):
    id: str
    operator_id: str
    text: str
    value: str | None = None            # normalized value, machine-facing
    category: TraitCategory
    status: Literal["tentative", "established", "confirmed", "superseded"]
    evidence_count: int
    source_event_ids: list[str]
    created_at: datetime
    last_reinforced_at: datetime
    superseded_by: str | None = None


class OperatorProfile(BaseModel):
    operator_id: str
    active_items: list[MemoryItem]


class Session(BaseModel):
    id: str
    operator_id: str
    opened_at: datetime
    closed_at: datetime | None = None
    trigger_alarm_code: str | None = None
    machine_id: str | None = None
    status: Literal["open", "resolved", "escalated", "abandoned"] = "open"


class Hypothesis(BaseModel):
    id: str
    operator_id: str | None = None
    kind: Literal["behavioural_pattern", "tacit_knowledge"]
    description: str
    evidence_count: int = 1
    status: Literal["proposed", "accepted", "rejected", "promoted"] = "proposed"
    source_event_ids: list[str] = []
    created_at: datetime
