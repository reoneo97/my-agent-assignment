from __future__ import annotations

import json

from pydantic_ai import Agent

from ola.agents.provider import make_model

_SYSTEM = """\
You are a manufacturing shopfloor assistant. You help operators troubleshoot alarms,
answer questions, and complete tasks. You receive a context bundle containing:
- The operator's message
- Prior turns this session
- A knowledge-graph context (procedure, disposition, related alarms, skills)
- A profile of the operator's known behavioural traits (tier-tagged)
- A personalization directive (controls tone, scaffolding, escalation posture)
- Optionally a validation directive (ask a specific confirmation question)

Follow the directives precisely. Keep responses practical and concise.
When a validation directive is present, weave the question naturally into the reply —
do NOT ask multiple confirmation questions at once.
Never add friction to escalation; always make it easy for the operator to get help.
"""

_agent: Agent[None, str] = Agent(make_model(), output_type=str, system_prompt=_SYSTEM)


def _build_prompt_from_bundle(bundle: "ContextBundle") -> str:  # type: ignore[name-defined]
    session_thread_text = ""
    if bundle.session_thread:
        lines = [f"  [{t['role']}] {t['content']}" for t in bundle.session_thread[-6:]]
        session_thread_text = "\n".join(lines)

    kg_text = json.dumps(bundle.kg_context, indent=2) if bundle.kg_context else "(no KG context)"

    profile_text = "\n".join(
        f"  [{i['status']}] ({i['category']}) {i['text']}"
        for i in bundle.relevant_profile_items
    ) or "  (no profile yet)"

    validation_block = (
        f"\n=== VALIDATION DIRECTIVE ===\n{bundle.validation_directive}"
        if bundle.validation_directive
        else ""
    )

    return f"""\
=== OPERATOR PROFILE (situation-relevant slice) ===
{profile_text}

=== SYNOPSIS ===
{bundle.synopsis or "(none yet)"}

=== KG CONTEXT ===
{kg_text}

=== SESSION THREAD (recent turns) ===
{session_thread_text or "(first turn)"}

=== PERSONALIZATION DIRECTIVE ===
{bundle.personalization_directive}
{validation_block}

=== OPERATOR MESSAGE ===
{bundle.operator_message}

Respond to the operator.
"""


async def generate_response_from_bundle(bundle: "ContextBundle") -> str:  # type: ignore[name-defined]
    from ola.context_assembler import ContextBundle  # local import avoids circular
    result = await _agent.run(_build_prompt_from_bundle(bundle))
    return result.output


# ── Legacy helpers (used by demo.py and stream_interaction) ──────────────────

def _build_prompt(content: str, profile_block: str, directive: str, alarm_code: str | None = None, event_type: str = "question") -> str:
    return f"""\
=== OPERATOR PROFILE ===
{profile_block}

=== POLICY DIRECTIVE ===
{directive}

=== CURRENT INTERACTION ===
Event type: {event_type}
Alarm code: {alarm_code}
Operator message: {content}

Respond to the operator following the profile and directive above.
"""


async def generate_response(content: str, profile_block: str, directive: str, alarm_code: str | None = None, event_type: str = "question") -> str:
    result = await _agent.run(_build_prompt(content, profile_block, directive, alarm_code, event_type))
    return result.output


from collections.abc import AsyncIterator  # noqa: E402


async def stream_response(content: str, profile_block: str, directive: str) -> AsyncIterator[str]:
    async with _agent.run_stream(_build_prompt(content, profile_block, directive)) as result:
        async for chunk in result.stream_text(delta=True):
            yield chunk
