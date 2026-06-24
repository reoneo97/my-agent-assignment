"""
LLM-simulated manufacturing operators with hidden ground-truth traits.
Ground truth stays server-side; only produced OperatorInteractions are exposed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.events import OperatorInteraction

# ── Safe operator metadata (no ground-truth traits) ───────────────────────────
# This is the only persona data the API exposes to the client.

OPERATORS = [
    {"id": "op-demo-01", "name": "Maya",  "machine_type": "DieAttach"},
    {"id": "op-demo-02", "name": "Raj",   "machine_type": "WireBond"},
]

# ── Hidden ground-truth traits (evaluation seeds for Stage 3) ─────────────────
# Never returned to the client. The pipeline only sees produced interaction text.

_GROUND_TRUTH: dict[str, dict] = {
    "op-demo-01": {
        "name": "Maya",
        "early_traits": {
            "instruction_modality": "visual, step-by-step diagrams",
            "escalation": "escalates complex faults quickly, handles basic alarms independently",
            "troubleshooting": "checks display panel first, then manuals",
            "issue_confidence": "confident on basic pressure/flow alarms, uncertain on hydraulics",
            "shift": "day",
        },
        "drift_after_interaction": 5,
        "drifted_traits": {
            "instruction_modality": "prefers concise text steps, no longer needs diagrams",
            "escalation": "now attempts to self-resolve more complex faults before escalating",
        },
        "scenarios": [
            ("alarm",    "PA-2201", "High pressure alarm on Line 2"),
            ("question", None,      "How to calibrate flow sensor on Unit 4?"),
            ("task",     None,      "Pre-shift checklist on packaging line"),
            ("alarm",    "HY-0042", "Hydraulic fault on press B"),
            ("question", None,      "Which manual covers the PA-2200 series?"),
            ("alarm",    "PA-2201", "High pressure alarm again — same unit"),
            ("task",     None,      "End-of-day shutdown procedure for Line 2"),
            ("alarm",    "HY-0042", "Hydraulic fault — different press (press C)"),
            ("question", None,      "Troubleshooting guide for intermittent flow sensor errors"),
            ("alarm",    "FL-1105", "Flow sensor anomaly on Unit 4"),
        ],
    },
    "op-demo-02": {
        "name": "Raj",
        "early_traits": {
            "instruction_modality": "prefers concise text, minimal diagrams",
            "escalation": "rarely escalates — tries to resolve independently first",
            "troubleshooting": "reads error codes directly, checks manual only if stuck",
            "issue_confidence": "highly confident on wire-bond faults, less so on recipe issues",
            "shift": "night",
        },
        "drift_after_interaction": 6,
        "drifted_traits": {
            "escalation": "has started escalating hydraulic faults after a near-miss incident",
        },
        "scenarios": [
            ("alarm",    "HY-0042", "Hydraulic fault on Press A — night shift"),
            ("question", None,      "What is the reset sequence for HY-0043?"),
            ("task",     None,      "Start-of-shift machine inspection routine"),
            ("alarm",    "RC-3301", "Recipe parameter alarm on FlipChip line"),
            ("question", None,      "Where do I find the wire-bond calibration log?"),
            ("alarm",    "HY-0042", "Hydraulic fault again — Press D this time"),
            ("task",     None,      "End-of-night shutdown for WireBond line"),
            ("alarm",    "SN-0710", "Sensor anomaly on FlipChip unit"),
            ("question", None,      "Best approach for recurring HY-0043 faults?"),
            ("alarm",    "FL-1105", "Flow sensor alarm — carried over from day shift"),
        ],
    },
}

_SYSTEM = """\
You are simulating a manufacturing shopfloor operator named {name}.
You have the following behavioural traits at this stage:
{traits_text}

Generate a realistic operator interaction for the current situation.
The interaction should be consistent with your traits — do not break character.
Keep the raw_text to 2-4 sentences, first-person.
"""


class InteractionSpec(BaseModel):
    event_type: str
    alarm_code: str | None
    shift: str
    outcome: str
    raw_text: str


# ── Per-operator interaction counter (in-memory; resets on server restart) ────
_counters: dict[str, int] = {}


def get_operators() -> list[dict]:
    """Return safe operator metadata — no ground-truth traits."""
    return OPERATORS


async def get_next_interaction(operator_id: str) -> OperatorInteraction:
    """Generate the next scenario interaction for the given operator."""
    gt = _GROUND_TRUTH.get(operator_id)
    if gt is None:
        raise ValueError(f"Unknown operator: {operator_id}")

    scenarios = gt["scenarios"]
    idx = _counters.get(operator_id, 0)
    _counters[operator_id] = (idx + 1) % len(scenarios)

    event_type, alarm_code, situation = scenarios[idx]
    drift_at: int = gt["drift_after_interaction"]
    name: str = gt["name"]

    traits = {**gt["early_traits"]}
    if idx >= drift_at:
        traits.update(gt["drifted_traits"])

    traits_text = "\n".join(f"  - {k}: {v}" for k, v in traits.items())
    system = _SYSTEM.format(name=name, traits_text=traits_text)

    agent: Agent[None, InteractionSpec] = Agent(
        make_model(), output_type=InteractionSpec, system_prompt=system
    )
    result = await agent.run(
        f"Situation: {situation}\n"
        f"Interaction number: {idx + 1} of {len(scenarios)}\n"
        "Generate the operator's interaction for this situation."
    )
    spec = result.output

    return OperatorInteraction(
        id=str(uuid.uuid4()),
        operator_id=operator_id,
        timestamp=datetime.now(timezone.utc),
        shift=spec.shift if spec.shift in ("day", "night") else gt["early_traits"].get("shift", "day"),  # type: ignore[arg-type]
        event_type=spec.event_type or event_type,
        alarm_code=alarm_code,
        raw_text=spec.raw_text,
        outcome=spec.outcome,
    )


def reset_counter(operator_id: str) -> None:
    _counters[operator_id] = 0


def get_eval_ground_truth(operator_id: str) -> dict | None:
    """Return hidden ground truth for eval endpoint only. Never call from learning pipeline."""
    return _GROUND_TRUTH.get(operator_id)


async def simulate_interactions(n: int = 10, operator_id: str = "op-demo-01") -> AsyncIterator[OperatorInteraction]:
    """Async generator for the CLI demo driver."""
    for _ in range(n):
        yield await get_next_interaction(operator_id)
