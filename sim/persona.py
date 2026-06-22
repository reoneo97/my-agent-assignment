"""
LLM-simulated manufacturing operator with hidden ground-truth traits.
The ground-truth is visible here but not exposed to the learning system.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.events import OperatorInteraction

# ── Hidden ground-truth traits ──────────────────────────────────────────────
# These are the evaluation seeds for Stage 3; the rest of the system never sees them.
GROUND_TRUTH = {
    "operator_id": "op-maya-01",
    "name": "Maya",
    "early_traits": {
        "instruction_modality": "visual, step-by-step diagrams",
        "escalation": "escalates complex faults quickly, handles basic alarms independently",
        "troubleshooting": "checks display panel first, then manuals",
        "issue_confidence": "confident on basic pressure/flow alarms, uncertain on hydraulics",
        "shift": "day",
    },
    # Trait that changes midway (to exercise SUPERSEDE / drift detection)
    "drift_after_interaction": 5,
    "drifted_traits": {
        "instruction_modality": "prefers concise text steps after gaining experience, no longer needs diagrams",
        "escalation": "now attempts to self-resolve more complex faults before escalating",
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


async def simulate_interactions(n: int = 10) -> AsyncIterator[OperatorInteraction]:
    """
    Yield n OperatorInteraction objects from the simulated persona.
    Traits drift after GROUND_TRUTH['drift_after_interaction'] interactions.
    """
    op_id = GROUND_TRUTH["operator_id"]
    name = GROUND_TRUTH["name"]
    drift_at = GROUND_TRUTH["drift_after_interaction"]

    scenarios = [
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
    ]

    base_time = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)

    for i in range(min(n, len(scenarios))):
        event_type, alarm_code, situation = scenarios[i]

        # Determine active traits
        if i < drift_at:
            traits = {**GROUND_TRUTH["early_traits"]}
        else:
            traits = {**GROUND_TRUTH["early_traits"], **GROUND_TRUTH["drifted_traits"]}

        traits_text = "\n".join(f"  - {k}: {v}" for k, v in traits.items())
        system = _SYSTEM.format(name=name, traits_text=traits_text)

        agent: Agent[None, InteractionSpec] = Agent(
            make_model(),
            output_type=InteractionSpec,
            system_prompt=system,
        )

        prompt = (
            f"Situation: {situation}\n"
            f"Interaction number: {i + 1} of {n}\n"
            "Generate the operator's interaction for this situation."
        )

        result = await agent.run(prompt)
        spec = result.output

        yield OperatorInteraction(
            id=str(uuid.uuid4()),
            operator_id=op_id,
            timestamp=base_time + timedelta(hours=i),
            shift=spec.shift if spec.shift in ("day", "night") else "day",  # type: ignore[arg-type]
            event_type=spec.event_type or event_type,
            alarm_code=alarm_code,
            raw_text=spec.raw_text,
            outcome=spec.outcome,
        )
