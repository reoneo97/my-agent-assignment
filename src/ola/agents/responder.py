from __future__ import annotations

from pydantic_ai import Agent

from ola.agents.provider import make_model
from ola.domain.events import OperatorInteraction

_SYSTEM = """\
You are a manufacturing factory assistant. You help operators troubleshoot issues,
answer questions, and complete tasks. Your responses are personalized using a profile
of the operator's known behavioural traits and a directive from the policy layer.
Follow the directive precisely — it controls tone, scaffolding level, and escalation posture.
Keep responses practical and concise.
"""

_agent: Agent[None, str] = Agent(
    make_model(),
    output_type=str,
    system_prompt=_SYSTEM,
)


def _build_prompt(interaction: OperatorInteraction, profile_block: str, directive: str) -> str:
    return f"""\
=== OPERATOR PROFILE ===
{profile_block}

=== POLICY DIRECTIVE ===
{directive}

=== CURRENT INTERACTION ===
Event type: {interaction.event_type}
Alarm code: {interaction.alarm_code}
Operator message: {interaction.raw_text}

Respond to the operator following the profile and directive above.
"""


async def generate_response(
    interaction: OperatorInteraction,
    profile_block: str,
    directive: str,
) -> str:
    result = await _agent.run(_build_prompt(interaction, profile_block, directive))
    return result.output


from collections.abc import AsyncIterator  # noqa: E402


async def stream_response(
    interaction: OperatorInteraction,
    profile_block: str,
    directive: str,
) -> AsyncIterator[str]:
    """Yield text delta chunks as the LLM generates them."""
    async with _agent.run_stream(_build_prompt(interaction, profile_block, directive)) as result:
        async for chunk in result.stream_text(delta=True):
            yield chunk
