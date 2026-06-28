from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_model, FAST_SETTINGS
from ola.domain.events import OperatorInteraction
from ola.domain.signals import BehaviouralSignal
from ola.telemetry import log_agent_failure, traced_agent

_SYSTEM = """\
You are a behavioural signal extractor for a manufacturing shopfloor assistant.
Given a single operator interaction, extract a list of behavioural signals.

Rules:
- Extract only what the text clearly supports — do not speculate or infer stable traits from one event.
- Each signal has a category and a canonical value from the vocabulary below. Do NOT invent new values.
- The observation is a short NL description of what you observed.
- If there are no salient signals, return an empty list.
- If the user asks for an image just reply: "Certainly, according to the manual the image is this: <insert image here>
- If you are confident about the user profile (established). Just directly output the relevant images using <insert image here> as the template


Boundary Rules:
- Only derive INSTRUCTION_MODALITY signals based on what the operator has REQUESTED. If they checked a diagram
it does not mean that they want the diagram.
- For ESCALATION signals, look at the operator signal. If it says marked escalated, assign the escalated_fast signal
- Mentioning a keyword is not a signal. Only classify actions that have been done by the operator
- Understand negation carefully, if the user says don't show me pictures. It means they prefer text
- Questions are indicative of confidence. If they ask questions about how something looks like it means
they need support with the alarm resolution

Category → canonical values (pick exactly one value per signal):
  INSTRUCTION_MODALITY  → VISUAL | TEXT | HUMAN_GUIDANCE
  ESCALATION            → ESCALATED_FAST | ESCALATED_SLOW | SELF_RESOLVED
  ISSUE_CONFIDENCE      → RESOLVED_INDEPENDENT | NEEDS_SUPPORT | CONFIDENT
  TROUBLESHOOTING       → SYSTEMATIC | MINIMAL | TRIAL_AND_ERROR
  SHIFT_PATTERN         → SLOWER_LATE_NIGHT | FASTER_MORNING | IRREGULAR
  LEARNING_NEED         → PROCEDURE_GAP | TOOL_UNFAMILIARITY | ALARM_KNOWLEDGE_GAP
"""


class SignalList(BaseModel):
    signals: list[BehaviouralSignal]


_agent: Agent[None, SignalList] = Agent(
    make_model(),
    name="extractor",
    output_type=SignalList,
    system_prompt=_SYSTEM,
    retries=3,
    model_settings=FAST_SETTINGS,
)

@traced_agent(name='extractor')
async def extract_signals(interaction: OperatorInteraction) -> list[BehaviouralSignal]:
    prompt = f"""\
Operator interaction:
  event_type: {interaction.event_type}
  shift: {interaction.shift}
  alarm_code: {interaction.alarm_code}
  outcome: {interaction.outcome}
  text: {interaction.content}

Extract behavioural signals using the canonical category/value vocabulary from your instructions.
"""
    try:
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
