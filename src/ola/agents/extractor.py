from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.events import OperatorInteraction
from ola.domain.signals import BehaviouralSignal

_SYSTEM = """\
You are a behavioural signal extractor for a manufacturing assistant.
Given a single operator interaction, extract a list of behavioural signals.
Each signal must identify a specific observable trait with category, short observation, and a normalized value.
Be concise. Extract only what the text clearly supports — do not speculate.
If there are no salient signals, return an empty list.
"""

_CATEGORIES = (
    "INSTRUCTION_MODALITY | ESCALATION | TROUBLESHOOTING | "
    "SHIFT_PATTERN | LEARNING_NEED | ISSUE_CONFIDENCE"
)


class SignalList(BaseModel):
    signals: list[BehaviouralSignal]


_agent: Agent[None, SignalList] = Agent(
    make_model(),
    output_type=SignalList,
    system_prompt=_SYSTEM,
)


async def extract_signals(interaction: OperatorInteraction) -> list[BehaviouralSignal]:
    prompt = f"""\
Operator interaction:
  event_type: {interaction.event_type}
  shift: {interaction.shift}
  alarm_code: {interaction.alarm_code}
  outcome: {interaction.outcome}
  text: {interaction.content}

Valid categories: {_CATEGORIES}

Extract behavioural signals. Set source_event_id = "{interaction.id}" on each.
"""
    result = await _agent.run(prompt)
    signals = result.output.signals
    # Ensure provenance
    for s in signals:
        s.source_event_id = interaction.id
    return signals
