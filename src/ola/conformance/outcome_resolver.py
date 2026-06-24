"""
Outcome Resolver — deterministic batch step, runs during consolidation.

For PENDING conformance events whose review window has elapsed (simulated/
shortened for the demo), synthesises an outcome_quality and routes
divergent+good-outcome cases to the review queue.

Production framing: in production the outcome window is the real post-resolution
measurement period (downtime, recurrence); here it is simulated as immediately
available to make the demo runnable without waiting.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ola.memory.store import get_pending_conformance_events, resolve_conformance_event


_QUADRANT_MAP = {
    ("conformant",  "good"): "competent_baseline",
    ("conformant",  "bad"):  "sop_inadequate",
    ("divergent",   "good"): "tacit_knowledge_candidate",
    ("divergent",   "bad"):  "worker_error_skill_gap",
}


def _simulate_outcome(expected_disposition: str | None, observed_outcome: str | None) -> tuple[str, str]:
    """
    Simulate conformance + outcome_quality from available metadata.
    In production: compare observed action to procedure steps; measure machine window.
    """
    disp = (expected_disposition or "EITHER").upper()
    outcome_str = observed_outcome or "unresolved"

    # Conformance: did the operator do what was expected?
    if disp == "ESCALATE" and outcome_str == "resolved_independently":
        conformance = "divergent"
    elif disp == "SELF_RESOLVE" and outcome_str == "escalated":
        conformance = "divergent"
    else:
        conformance = "conformant"

    # Outcome quality: simplified — independent resolution is good; unresolved is bad
    if outcome_str == "resolved_independently":
        quality = "good"
    elif outcome_str == "escalated":
        quality = "good"  # escalation is also a valid outcome
    else:
        quality = "bad"

    return conformance, quality


def resolve_pending(operator_id: str, db_path: str | None = None) -> list[dict]:
    """
    Resolve all pending conformance events for an operator.
    Returns list of resolved event dicts for logging/UI.
    """
    kwargs = {"db_path": db_path} if db_path else {}
    pending = get_pending_conformance_events(operator_id, **kwargs)
    resolved = []

    for evt in pending:
        conformance, quality = _simulate_outcome(
            evt.get("expected_disposition"),
            evt.get("observed_action"),
        )
        quadrant = _QUADRANT_MAP.get((conformance, quality), "unknown")

        resolve_conformance_event(
            event_id=evt["id"],
            conformance=conformance,
            observed_action=evt.get("observed_action") or "inferred from outcome",
            outcome_quality=quality,
            quadrant=quadrant,
            **kwargs,
        )
        resolved.append({
            "id": evt["id"],
            "alarm_code": evt.get("alarm_code"),
            "conformance": conformance,
            "outcome_quality": quality,
            "quadrant": quadrant,
            "routes_to_review": quadrant == "tacit_knowledge_candidate",
        })

    return resolved
