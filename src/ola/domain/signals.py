from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class TraitCategory(str, Enum):
    INSTRUCTION_MODALITY = "INSTRUCTION_MODALITY"
    ESCALATION = "ESCALATION"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    SHIFT_PATTERN = "SHIFT_PATTERN"
    LEARNING_NEED = "LEARNING_NEED"
    ISSUE_CONFIDENCE = "ISSUE_CONFIDENCE"


class BehaviouralSignal(BaseModel):
    category: TraitCategory
    observation: str  # short NL description
    value: str  # normalized value, e.g. "VISUAL", "ESCALATED_FAST"
    source_event_id: str
