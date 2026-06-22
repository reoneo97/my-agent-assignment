from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OperatorInteraction(BaseModel):
    id: str
    operator_id: str
    timestamp: datetime
    shift: Literal["day", "night"] | None = None
    event_type: str  # e.g. "alarm", "question", "task"
    alarm_code: str | None = None
    raw_text: str
    outcome: str | None = None  # e.g. "resolved_independently", "escalated"
