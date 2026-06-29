"""
Reviewer — per-session/per-shift, strong model. Two distinct sub-tasks:
  1. review_conversation: full turn-marked conversation + profile → longer-range
     BehaviouralSignals (escalation / troubleshooting / shift patterns) + Hypotheses.
     Signals are written into the profile via the Memory Manager (one arbiter for
     all profile writes), NOT emitted as memory operations directly.
  2. synopsis: current profile + recent events → updated operator synopsis paragraph

Local signals (instruction modality / issue confidence / learning needs) are the
Extractor's job on the hot path; the Reviewer never re-derives them. Conformance
is deterministic (conformance/router.py + outcome_resolver.py) — no agent here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from ola.agents.provider import make_strong_model, STRONG_SETTINGS
from ola.domain.memory import Hypothesis, OperatorProfile
from ola.domain.signals import BehaviouralSignal, TraitCategory
from ola.telemetry import traced_agent

_model = make_strong_model()

# ── Scope → allowed (longer-range) categories ─────────────────────────────────
# Local categories are owned by the Extractor and never produced here.
SESSION_CATEGORIES = {TraitCategory.TROUBLESHOOTING, TraitCategory.ESCALATION}
SHIFT_CATEGORIES = SESSION_CATEGORIES | {TraitCategory.SHIFT_PATTERN}


def _allowed_categories(scope: str) -> set[TraitCategory]:
    return SHIFT_CATEGORIES if scope == "shift" else SESSION_CATEGORIES


# ── Sub-schemas ───────────────────────────────────────────────────────────────

class ReviewerSignal(BaseModel):
    category: str  # TROUBLESHOOTING | ESCALATION | SHIFT_PATTERN
    value: str  # canonical value e.g. 'ESCALATED_FAST'
    observation: str  # short NL description of what was observed across the thread
    turn: int | None = None  # 1-based turn index the signal was inferred from


class ReviewerHypothesis(BaseModel):
    kind: Literal["behavioural_pattern", "tacit_knowledge"]
    description: str
    evidence_summary: str


class ReviewOutput(BaseModel):
    signals: list[ReviewerSignal]
    hypotheses: list[ReviewerHypothesis]


# ── Agent ─────────────────────────────────────────────────────────────────────

_review_agent: Agent[None, ReviewOutput] = Agent(
    _model,
    name="reviewer.review_conversation",
    output_type=ReviewOutput,
    retries=3,
    model_settings=STRONG_SETTINGS,
    system_prompt="""\
You are reviewing a FULL operator conversation to extract LONGER-RANGE behavioural
signals that cannot be judged from a single turn — they need the whole thread.

The conversation is given as turn-marked lines:
  [t<turn> | +<seconds>s | <role>/<event_type>] <text>
Use the turn index and elapsed time to reason about WHEN things happened
(e.g. an escalation early in the thread is fast; one after many turns is slow).

Extract only what the thread clearly supports. Each signal has a category and a
canonical value from the vocabulary below — do NOT invent new values, and do NOT
emit any category outside the allowed set you are told to use. Set `turn` to the
1-based turn index the signal was inferred from. If nothing is salient, return an
empty signal list.

Category → canonical values:
  ESCALATION       → ESCALATED_FAST | ESCALATED_SLOW | SELF_RESOLVED
  TROUBLESHOOTING  → SYSTEMATIC | MINIMAL | TRIAL_AND_ERROR
  SHIFT_PATTERN    → SLOWER_LATE_NIGHT | FASTER_MORNING | IRREGULAR

Escalation guidance:
- ESCALATED_FAST: operator escalates early / with little independent attempt.
- ESCALATED_SLOW: operator works the problem over several turns before escalating.
- SELF_RESOLVED: operator resolves without escalating.

Also flag any novel recurring patterns or tacit-knowledge candidates not yet in the
profile as hypotheses (kind = behavioural_pattern | tacit_knowledge). Keep
descriptions to one sentence. Your output is observational; code rules decide tiers.
""",
)

_synopsis_agent: Agent[None, str] = Agent(
    _model,
    name="reviewer.synopsis",
    output_type=str,
    model_settings=STRONG_SETTINGS,
    system_prompt="""\
You are writing an operator behavioural synopsis for a manufacturing AI assistant.
Write a single paragraph (4-6 sentences) in third person describing the operator's
observable patterns: preferred instruction style, confidence on alarm types,
escalation behaviour, troubleshooting approach, and any learning needs.
Base it only on the provided profile items and recent events — do not speculate.
Be concrete and specific. If the profile is sparse, say so and note what is known.
""",
)


# ── Turn-marker rendering (context engineering) ───────────────────────────────

def _render_turns(turns: list[dict]) -> tuple[str, dict[int, str]]:
    """
    Render a conversation as turn-marked lines and return (text, turn→event_id map).

    Each turn becomes:
      [t<i> | +<seconds>s | <role>/<event_type>] <content>
    so the Reviewer can reason about ordering/timing (fast vs slow escalation).
    """
    if not turns:
        return "  (no turns)", {}

    def _ts(t: dict) -> datetime | None:
        raw = t.get("timestamp")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            return None

    base = next((_ts(t) for t in turns if _ts(t)), None)

    lines: list[str] = []
    turn_map: dict[int, str] = {}
    for i, t in enumerate(turns, start=1):
        ts = _ts(t)
        delta = int((ts - base).total_seconds()) if (ts and base) else 0
        role = t.get("role", "?")
        etype = t.get("event_type", "?")
        content = (t.get("content") or "")[:300]
        lines.append(f"  [t{i} | +{delta}s | {role}/{etype}] {content}")
        if t.get("id"):
            turn_map[i] = t["id"]
    return "\n".join(lines), turn_map


# ── Public API ────────────────────────────────────────────────────────────────

@traced_agent(name="reviewer.review_conversation")
async def review_conversation(
    turns: list[dict],
    profile: OperatorProfile,
    operator_id: str,
    scope: str,
    sentinel_event_id: str,
) -> tuple[list[BehaviouralSignal], list[Hypothesis]]:
    """
    Extract longer-range behavioural signals from a full conversation.

    Returns (list[BehaviouralSignal], list[Hypothesis]). The caller persists the
    signals and routes them through the Memory Manager to update the profile.
    `scope` ("session" | "shift") gates which categories are allowed.
    """
    allowed = _allowed_categories(scope)
    conversation, turn_map = _render_turns(turns)

    items_text = "\n".join(
        f"  [{i.id[:8]}] [{i.status}, n={i.evidence_count}] ({i.category.value}) {i.text}"
        for i in profile.active_items
    ) or "  (none)"

    allowed_names = ", ".join(sorted(c.value for c in allowed))
    prompt = (
        f"Scope: {scope}. Allowed signal categories: {allowed_names}.\n\n"
        f"Conversation (turn-marked):\n{conversation}\n\n"
        f"Current active profile:\n{items_text}\n\n"
        "Extract longer-range behavioural signals and any hypotheses from the thread above."
    )

    result = await _review_agent.run(prompt)
    out = result.output

    now = datetime.now(timezone.utc)
    signals: list[BehaviouralSignal] = []
    for rs in out.signals:
        try:
            category = TraitCategory(rs.category.strip().upper())
        except ValueError:
            continue
        if category not in allowed:
            continue  # never let the Reviewer emit local or out-of-scope categories
        source_event_id = turn_map.get(rs.turn or -1, sentinel_event_id)
        signals.append(
            BehaviouralSignal(
                category=category,
                value=rs.value,
                observation=rs.observation,
                source_event_id=source_event_id,
            )
        )

    hypotheses: list[Hypothesis] = [
        Hypothesis(
            id=str(uuid.uuid4()),
            operator_id=operator_id,
            kind=h.kind,
            description=h.description,
            created_at=now,
        )
        for h in out.hypotheses
    ]

    return signals, hypotheses


@traced_agent(name="reviewer.synopsis")
async def generate_synopsis(profile: OperatorProfile, recent_events: list[dict]) -> str:
    items_text = "\n".join(
        f"- [{i.status}, n={i.evidence_count}] ({i.category.value}) {i.text}"
        for i in profile.active_items
    ) or "(no profile items)"

    events_summary = "\n".join(
        f"  {e.get('event_type','?')}: {e.get('content','')[:150]}"
        for e in recent_events[-10:]
    )

    prompt = (
        f"Operator: {profile.operator_id}\n\n"
        f"Profile items:\n{items_text}\n\n"
        f"Recent interactions (sample):\n{events_summary}"
    )
    result = await _synopsis_agent.run(prompt)
    return result.output
