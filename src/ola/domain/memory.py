from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ola.domain.signals import TraitCategory


class MemoryOperation(BaseModel):
    id: str
    operator_id: str
    op_type: Literal["ADD", "REINFORCE", "SUPERSEDE", "NOOP"]
    target_item_id: str | None = None  # for REINFORCE / SUPERSEDE
    text: str | None = None  # for ADD / SUPERSEDE (the new belief)
    category: TraitCategory | None = None
    source_event_id: str
    timestamp: datetime


class MemoryItem(BaseModel):
    id: str
    operator_id: str
    text: str
    category: TraitCategory
    status: Literal["tentative", "established", "confirmed", "superseded"]
    evidence_count: int
    source_event_ids: list[str]
    created_at: datetime
    last_reinforced_at: datetime
    superseded_by: str | None = None


class OperatorProfile(BaseModel):
    operator_id: str
    active_items: list[MemoryItem]  # status != "superseded"
