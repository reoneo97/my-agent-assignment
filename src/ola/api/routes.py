from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ola.api.schemas import (
    AlarmOut,
    EvalResponse,
    InteractionRequest,
    InteractionResponse,
    InteractionOut,
    MemoryOpOut,
    MockAlarmRequest,
    MockAlarmResponse,
    OperatorsResponse,
    ProfileItemOut,
    ProfileOut,
    ShiftEndRequest,
    ShiftEndResponse,
    SignalOut,
    SynopsisOut,
    TraitMatch,
)
from ola.consolidation import run_consolidation
from ola.memory.store import get_profile, get_synopsis, reset_operator
from ola.pipeline import process_interaction
from ola.sessions import open_alarm_session

router = APIRouter()

_DB = os.environ.get("OLA_DB_PATH", "ola.db")


def _profile_out(operator_id: str) -> ProfileOut:
    profile = get_profile(operator_id, db_path=_DB)
    return ProfileOut(
        operator_id=operator_id,
        items=[
            ProfileItemOut(
                id=item.id,
                text=item.text,
                category=item.category.value,
                status=item.status,
                evidence_count=item.evidence_count,
                source_event_ids=item.source_event_ids,
                last_updated=item.last_reinforced_at,
            )
            for item in profile.active_items
        ],
    )


# ── POST /api/interaction ─────────────────────────────────────────────────────

@router.post("/api/interaction", response_model=InteractionResponse)
async def interaction(req: InteractionRequest) -> InteractionResponse:
    from sim.persona import get_next_interaction

    if req.source == "simulated":
        interaction_obj = await get_next_interaction(req.operator_id)
    else:
        if not req.message and not req.outcome:
            raise HTTPException(status_code=422, detail="message is required when source=user")
        from ola.domain.events import OperatorInteraction
        import uuid
        content = req.message
        if not content and req.outcome:
            content = f"Marked {req.outcome.replace('_', ' ')}."
        interaction_obj = OperatorInteraction(
            id=str(uuid.uuid4()),
            operator_id=req.operator_id,
            timestamp=datetime.now(timezone.utc),
            shift="day",
            event_type="resolution_action" if req.outcome else "question",
            outcome=req.outcome,
            content=content,
        )

    signals, ops, profile, reply = await process_interaction(interaction_obj, db_path=_DB)

    return InteractionResponse(
        interaction=InteractionOut(
            id=interaction_obj.id,
            operator_message=interaction_obj.content,
            timestamp=interaction_obj.timestamp,
            alarm_code=interaction_obj.alarm_code,
            shift=interaction_obj.shift,
        ),
        assistant_reply=reply,
        signals_extracted=[
            SignalOut(category=s.category.value, value=s.value, observation=s.observation)
            for s in signals
        ],
        memory_operations=[
            MemoryOpOut(
                op_type=op.op_type,
                target_item_id=op.target_item_id,
                text=op.text,
                category=op.category.value if op.category else None,
            )
            for op in ops
        ],
        profile=_profile_out(req.operator_id),
    )


# ── POST /api/alarm/mock ──────────────────────────────────────────────────────

@router.post("/api/alarm/mock", response_model=MockAlarmResponse)
async def mock_alarm(req: MockAlarmRequest) -> MockAlarmResponse:
    result = await open_alarm_session(req.operator_id, db_path=_DB)
    kg = result["kg_context"]
    return MockAlarmResponse(
        session_id=result["session_id"],
        alarm=AlarmOut(
            code=result["alarm_code"],
            machine_id=result["machine_id"],
            complexity=kg.get("complexity"),
            severity=kg.get("severity"),
            expected_disposition=kg.get("expected_disposition"),
        ),
        system_message=f"Alarm {result['alarm_code']} fired on {result['machine_id'] or 'an unspecified machine'}.",
        proactive_reply=result["proactive_message"],
    )


# ── POST /api/shift/end ───────────────────────────────────────────────────────

@router.post("/api/shift/end", response_model=ShiftEndResponse)
async def shift_end(req: ShiftEndRequest) -> ShiftEndResponse:
    return await run_consolidation(req.operator_id, db_path=_DB)


# ── GET /api/profile/{operator_id} ───────────────────────────────────────────

@router.get("/api/profile/{operator_id}", response_model=ProfileOut)
async def profile(operator_id: str) -> ProfileOut:
    return _profile_out(operator_id)


# ── GET /api/synopsis/{operator_id} ──────────────────────────────────────────

@router.get("/api/synopsis/{operator_id}", response_model=SynopsisOut)
async def synopsis(operator_id: str) -> SynopsisOut:
    row = get_synopsis(operator_id, db_path=_DB)
    if not row:
        return SynopsisOut(
            text=f"No synopsis yet for {operator_id}.",
            generated_at=datetime.now(timezone.utc),
            version=0,
        )
    return SynopsisOut(
        text=row["text"],
        generated_at=datetime.fromisoformat(row["generated_at"]),
        version=row["version"],
    )


# ── GET /api/operators ────────────────────────────────────────────────────────

@router.get("/api/operators", response_model=OperatorsResponse)
async def operators() -> OperatorsResponse:
    from sim.persona import get_operators
    from ola.api.schemas import OperatorOut
    return OperatorsResponse(
        operators=[OperatorOut(**op) for op in get_operators()]
    )


# ── POST /api/reset/{operator_id} ────────────────────────────────────────────

@router.post("/api/reset/{operator_id}")
async def reset(operator_id: str) -> dict:
    from sim.persona import reset_counter
    from ola.consolidation import _last_profiles
    reset_operator(operator_id, db_path=_DB)
    reset_counter(operator_id)
    _last_profiles.pop(operator_id, None)
    return {"status": "ok", "operator_id": operator_id}


# ── GET /api/eval/{operator_id} ──────────────────────────────────────────────
# Reveal endpoint — server-computed inferred vs ground-truth comparison.
# Never fed back into the learning pipeline.

@router.get("/api/eval/{operator_id}", response_model=EvalResponse)
async def eval_operator(operator_id: str) -> EvalResponse:
    from sim.persona import get_eval_ground_truth

    gt = get_eval_ground_truth(operator_id)
    if not gt:
        raise HTTPException(status_code=404, detail="No ground truth for this operator")

    profile = get_profile(operator_id, db_path=_DB)
    inferred_texts = [item.text.lower() for item in profile.active_items]

    all_traits = {**gt["early_traits"], **gt.get("drifted_traits", {})}

    matched: list[TraitMatch] = []
    missed: list[TraitMatch] = []

    for trait_key, trait_val in all_traits.items():
        keywords = [w for w in trait_val.lower().split() if len(w) > 4]
        match_text = next(
            (t for t in inferred_texts if any(kw in t for kw in keywords)),
            None,
        )
        entry = TraitMatch(
            trait=trait_val,
            category=trait_key.upper(),
            matched=match_text is not None,
            inferred_text=match_text,
        )
        (matched if entry.matched else missed).append(entry)

    inferred_categories = {item.category.value for item in profile.active_items}
    gt_categories = {k.upper() for k in all_traits}
    spurious = [
        item.text for item in profile.active_items
        if item.category.value not in gt_categories
    ]

    total = len(matched) + len(missed) + len(spurious)
    score = len(matched) / total if total else 0.0

    return EvalResponse(
        operator_id=operator_id,
        matched=matched,
        missed=missed,
        spurious=spurious,
        score=round(score, 2),
    )


# ── GET /api/health ───────────────────────────────────────────────────────────

@router.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
