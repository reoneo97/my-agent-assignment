"""
run_consolidation() — slow-path batch on the strong-model clock; never blocks the
hot path. Runs at two granularities:
  - scope="session" (End Session): extract+apply SESSION-level signals only; no
    synopsis regen (deferred to End Shift).
  - scope="shift"   (End Shift):   extract+apply SESSION + SHIFT-level signals and
    regenerate the synopsis.

Steps:
  1. Reviewer.review_conversation → longer-range BehaviouralSignals + hypotheses
  2. Persist signals → Memory Manager → memory_operations (one arbiter for writes)
  3. Outcome Resolver → resolve PENDING conformance events → fill 2×2
  4. Tier recompute (implicit in fold) → Projection of newly-established items
  5. (shift only) Reviewer.synopsis → regenerate operator_synopsis → bump version
  6. Return before/after diff
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ola.agents.memory_manager import decide_operations
from ola.agents.reviewer import review_conversation
from ola.agents.reviewer import generate_synopsis as reviewer_synopsis
from ola.api.schemas import (
    ProfileItemOut,
    ProfileOut,
    ShiftChanges,
    ShiftEndResponse,
    SupersededRef,
    TierTransition,
)
from ola.conformance.outcome_resolver import resolve_pending
from ola.domain.memory import OperatorProfile
from ola.kg.projection import project_profile
from ola.memory.store import (
    append_hypothesis,
    append_operation,
    append_signal,
    get_profile,
    get_recent_events,
    get_session_thread,
)
from ola.memory.synopsis import save_synopsis


def _to_profile_out(profile: OperatorProfile) -> ProfileOut:
    return ProfileOut(
        operator_id=profile.operator_id,
        items=[
            ProfileItemOut(
                id=i.id, text=i.text, category=i.category.value, status=i.status,
                evidence_count=i.evidence_count, source_event_ids=i.source_event_ids,
                last_updated=i.last_reinforced_at,
            )
            for i in profile.active_items
        ],
    )


def _diff(before: OperatorProfile, after: OperatorProfile) -> ShiftChanges:
    before_map = {i.id: i for i in before.active_items}
    after_map = {i.id: i for i in after.active_items}

    transitions = [
        TierTransition(item_id=iid, from_status=before_map[iid].status, to_status=item.status)
        for iid, item in after_map.items()
        if iid in before_map and before_map[iid].status != item.status
    ]
    new_items = [
        ProfileItemOut(
            id=i.id, text=i.text, category=i.category.value, status=i.status,
            evidence_count=i.evidence_count, source_event_ids=i.source_event_ids,
            last_updated=i.last_reinforced_at,
        )
        for iid, i in after_map.items()
        if iid not in before_map
    ]
    superseded = [
        SupersededRef(item_id=iid, by="(superseded this shift)")
        for iid in before_map
        if iid not in after_map
    ]
    return ShiftChanges(tier_transitions=transitions, new_items=new_items, superseded=superseded)


# In-memory snapshot of profile at last consolidation per operator (fine for demo).
_last_profiles: dict[str, OperatorProfile] = {}


async def run_consolidation(
    operator_id: str,
    scope: str = "shift",
    session_id: str | None = None,
    db_path: str | None = None,
) -> ShiftEndResponse:
    kwargs = {"db_path": db_path} if db_path else {}

    profile_before = _last_profiles.get(
        operator_id, OperatorProfile(operator_id=operator_id, active_items=[])
    )
    profile_current = get_profile(operator_id, **kwargs)

    # 1. Gather the conversation to review.
    #    session scope → just this session's thread (all roles, ordered, ideal for
    #    turn markers); shift scope → recent operator events across the shift.
    if scope == "session" and session_id:
        turns = get_session_thread(session_id, **kwargs)
    else:
        # get_recent_events returns newest-first; reverse to chronological order.
        turns = list(reversed(get_recent_events(operator_id, limit=50, **kwargs)))
    sentinel_event_id = turns[-1]["id"] if turns else "no-events"

    # 2. Reviewer extracts longer-range signals → Memory Manager → operations.
    if turns:
        signals, hypotheses = await review_conversation(
            turns=turns,
            profile=profile_current,
            operator_id=operator_id,
            scope=scope,
            sentinel_event_id=sentinel_event_id,
        )
        now = datetime.now(timezone.utc)
        for sig in signals:
            append_signal(
                signal_id=str(uuid.uuid4()),
                source_event_id=sig.source_event_id,
                operator_id=operator_id,
                category=sig.category.value,
                value=sig.value,
                observation=sig.observation,
                timestamp=now,
                **kwargs,
            )
        if signals:
            ops = await decide_operations(
                signals=signals,
                current_items=profile_current.active_items,
                operator_id=operator_id,
                source_event_id=sentinel_event_id,
                source="reviewer",
            )
            for op in ops:
                append_operation(op, **kwargs)
        for h in hypotheses:
            append_hypothesis(h, **kwargs)

    # 3. Outcome Resolver
    resolve_pending(operator_id, db_path=db_path)

    # 4. Recompute profile after reviewer ops + resolve, then project established items
    profile_after = get_profile(operator_id, **kwargs)
    project_profile(profile_after, profile_before)

    # 5. Synopsis — regenerated on End Shift only; End Session defers it.
    from ola.memory.store import get_synopsis
    synopsis_row = get_synopsis(operator_id, **kwargs)
    synopsis_before = synopsis_row["text"] if synopsis_row else f"No synopsis yet for {operator_id}."

    diff = _diff(profile_before, profile_after)
    no_updates = not (diff.tier_transitions or diff.new_items or diff.superseded)

    if scope != "shift" or (no_updates and not turns):
        synopsis_after = synopsis_before
    else:
        synopsis_after = await reviewer_synopsis(profile_after, turns)
        save_synopsis(operator_id, synopsis_after, db_path=db_path)

    _last_profiles[operator_id] = profile_after

    return ShiftEndResponse(
        no_significant_updates=no_updates,
        changes=diff,
        profile_before=_to_profile_out(profile_before),
        profile_after=_to_profile_out(profile_after),
        synopsis_before=synopsis_before,
        synopsis_after=synopsis_after,
    )
