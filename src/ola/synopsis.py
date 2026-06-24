from __future__ import annotations

from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.memory import OperatorProfile

_SYSTEM = """\
You are summarising what an AI assistant has learned about a manufacturing operator.
Write a single concise paragraph (3-5 sentences) describing their observable behavioural
patterns: preferred instruction style, escalation habits, confidence on different alarm
types, and any learning needs. Write in third person. Base it only on the provided profile
items — do not speculate beyond the evidence. If the profile is empty, say so briefly.
"""

_agent: Agent[None, str] = Agent(make_model(), output_type=str, system_prompt=_SYSTEM)


async def generate_synopsis(profile: OperatorProfile) -> str:
    if not profile.active_items:
        return f"No behavioural profile established yet for operator {profile.operator_id}."

    items_text = "\n".join(
        f"- [{item.status}, n={item.evidence_count}] ({item.category.value}) {item.text}"
        for item in profile.active_items
    )
    result = await _agent.run(
        f"Operator ID: {profile.operator_id}\n\nProfile items:\n{items_text}"
    )
    return result.output
