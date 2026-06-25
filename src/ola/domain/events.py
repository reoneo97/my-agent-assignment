from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class OperatorInteraction(BaseModel):
    id: str
    operator_id: str
    session_id: str = ""          # set by pipeline before appending
    role: Literal["operator", "assistant", "system"] = "operator"
    timestamp: datetime
    shift: Literal["day", "night"] | None = None
    machine_id: str | None = None
    event_type: str               # alarm | question | task | reply | confirmation_response
    alarm_code: str | None = None
    requested_modality: str | None = None
    content: str                  # raw message text (was raw_text in v1)
    outcome: Literal["resolved_independently", "escalated", "unresolved", "abandoned"] | None = None
