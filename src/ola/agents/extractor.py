from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.events import OperatorInteraction
from ola.domain.signals import BehaviouralSignal
from ola.telemetry import agent_span, log_agent_failure

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
    output_retries=3,
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
    try:
        async with agent_span("extractor"):
            result = await _agent.run(prompt)
        signals = result.output.signals
        for s in signals:
            s.source_event_id = interaction.id
        return signals
    except Exception as exc:
        log_agent_failure(
            agent_name="extractor",
            exc=exc,
            context={
                "operator_id": interaction.operator_id,
                "event_id": interaction.id,
                "event_type": interaction.event_type,
                "alarm_code": interaction.alarm_code,
                "content_preview": interaction.content[:200],
            },
            prompt=prompt,
        )
        return []
