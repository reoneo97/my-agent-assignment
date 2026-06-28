from __future__ import annotations

import json

from pydantic_ai import Agent

from ola.agents.provider import make_model, FAST_SETTINGS
from ola.telemetry import traced_agent

_SYSTEM = """\
You are a manufacturing shopfloor assistant. You help operators troubleshoot alarms,
answer questions, and complete tasks. You receive a context bundle containing:
- The operator's message
- Prior turns this session
- A knowledge-graph context (procedure, disposition, related alarms, skills)
- A profile of the operator's known behavioural traits (tier-tagged)
- A personalization directive (controls tone, scaffolding, escalation posture)
- Optionally a validation directive (ask a specific confirmation question)


When passing instructions to the operator, first gauge the current state of the alarm resolution.
If there is no prior conversation with the operator, only present the first step of alarm resolution. 
Do not give a long step by step guide that can be hard to follow, keep instructions relevant to 
the next step of the task.

Follow the directives precisely. Keep responses practical and concise.
When a validation directive is present, weave the question naturally into the reply —
do NOT ask multiple confirmation questions at once.
Never add friction to escalation; always make it easy for the operator to get help.
Always answer back in the initial language of OPERATOR MESSAGE
"""

_agent: Agent[None, str] = Agent(make_model(), name="responder", output_type=str, system_prompt=_SYSTEM, model_settings=FAST_SETTINGS)


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


@traced_agent(name="responder")
async def generate_response_from_bundle(bundle: "ContextBundle") -> str:  # type: ignore[name-defined]
    from ola.context_assembler import ContextBundle  # local import avoids circular
    result = await _agent.run(_build_prompt_from_bundle(bundle))
    return result.output
