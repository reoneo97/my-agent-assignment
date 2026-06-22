from __future__ import annotations

from typing import Literal

from ola.config import ESTABLISHED_THRESHOLD, TENTATIVE_THRESHOLD

Status = Literal["tentative", "established", "confirmed", "superseded"]


def assign_status(evidence_count: int, confirmed: bool = False) -> Status:
    """Pure function: count-based tier rule. Never calls LLM."""
    if confirmed:
        return "confirmed"
    if evidence_count >= ESTABLISHED_THRESHOLD:
        return "established"
    return "tentative"
