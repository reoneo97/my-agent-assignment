"""
Agent-level eval harness.

Runs structured-output evals against individual agents (Extractor, Memory Manager)
using hand-authored cases with deterministic scoring — no LLM judge needed.

Refactored onto mlflow.genai.evaluate(): each case becomes a dataset row
({"inputs", "expectations", "tags"}), predict_fn calls the agent, and a
@scorer function reuses the original pass/fail logic but returns a Feedback
object so failures are inspectable per-row in the MLflow UI/trace, not just
in stdout.

Three sets per agent:
  dev     — tune against these
  heldout — report final numbers here (don't tune to it)
  zh      — Mandarin input robustness (canonical enum values must not translate)

Usage:
  uv run python -m eval.run_agent_evals
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import mlflow  # noqa: E402
from mlflow.entities import Feedback  # noqa: E402
from mlflow.genai import scorer  # noqa: E402

from ola.telemetry import setup_tracing
from ola.agents.extractor import extract_signals
from ola.agents.memory_manager import decide_operations
from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryItem
from ola.domain.signals import BehaviouralSignal, TraitCategory
from eval.eval_sets import (
    EXTRACTOR_DEV,
    EXTRACTOR_HELDOUT,
    EXTRACTOR_ZH,
    MEMORY_MANAGER_DEV,
    MEMORY_MANAGER_HELDOUT,
    MEMORY_MANAGER_ZH,
)

setup_tracing()


# ── Case -> mlflow dataset row adapters ──────────────────────────────────────
#
# eval_sets.py keeps its original hand-authored shape (event/signals + expect_*
# fields per case). We adapt each case into the {"inputs", "expectations",
# "tags"} shape mlflow.genai.evaluate() expects, rather than rewriting the
# eval sets themselves.


def extractor_case_to_row(case: dict) -> dict:
    return {
        "inputs": {"event": case["event"]},
        "expectations": {
            "expect_signals": case.get("expect_signals", []),
            "must_not": case.get("must_not", []),
        },
        "tags": {"id": case["id"], "tests": case["tests"]},
    }


def memory_manager_case_to_row(case: dict) -> dict:
    expectations = {
        "expect_ops": case.get("expect_ops", []),
        "expect_op_any_of": case.get("expect_op_any_of", []),
        "must_not_op": case.get("must_not_op", []),
    }
    if "expect_op" in case:
        expectations["expect_op"] = case["expect_op"]
    return {
        "inputs": {
            "signals": case["signals"],
            "current_items": case.get("current_items", []),
        },
        "expectations": expectations,
        "tags": {"id": case["id"], "tests": case["tests"]},
    }


# ── predict_fn — wraps each agent so mlflow can call it per-row ─────────────
# mlflow.genai.evaluate() auto-detects async predict_fns and awaits them, and
# runs rows in a threadpool, so no asyncio.run/gather plumbing is needed here.


async def extractor_predict_fn(event: dict) -> list[dict]:
    interaction = OperatorInteraction(
        id=event.get("source_event_id", "eval-event"),
        operator_id="eval-operator",
        timestamp="2026-06-27T00:00:00Z",
        event_type=event["event_type"],
        alarm_code=event.get("alarm_code"),
        content=event["content"],
        outcome=event.get("outcome"),
        requested_modality=event.get("requested_modality"),
    )
    signals = await extract_signals(interaction)
    return [{"category": s.category.value, "value": s.value} for s in signals]


async def memory_manager_predict_fn(
    signals: list[dict], current_items: list[dict]
) -> list[dict]:
    behavioural_signals = [
        BehaviouralSignal(
            category=TraitCategory(s["category"]),
            value=s["value"],
            observation=s["observation"],
            source_event_id="eval-event",
        )
        for s in signals
    ]
    memory_items = [
        MemoryItem(
            id=item["id"],
            operator_id="eval-operator",
            text=item["text"],
            value=item["value"],
            category=TraitCategory(item["category"]),
            status=item["status"],
            evidence_count=item["evidence_count"],
            source_event_ids=[],
            created_at="2026-06-01T00:00:00Z",
            last_reinforced_at="2026-06-01T00:00:00Z",
            superseded_by=None,
        )
        for item in current_items
    ]
    ops = await decide_operations(
        signals=behavioural_signals,
        current_items=memory_items,
        operator_id="eval-operator",
        source_event_id="eval-event",
    )
    return [
        {"op_type": op.op_type, "target_item_id": op.target_item_id, "value": op.value}
        for op in ops
    ]


# ── Scorers — same pass/fail logic as before, now as Feedback ──────────────


def _matches_op(produced: dict, expected: dict) -> bool:
    if produced["op_type"].upper() != expected.get("op_type", "").upper():
        return False
    if (
        "target_item_id" in expected
        and produced["target_item_id"] != expected["target_item_id"]
    ):
        return False
    if "value" in expected and produced["value"] != expected["value"]:
        return False
    return True


@scorer
def extractor_correctness(outputs: list[dict], expectations: dict) -> Feedback:
    """Expected signals present, must_not signals absent, no fabrication."""
    details = []

    for expected in expectations.get("expect_signals", []):
        found = any(
            o["category"] == expected["category"] and o["value"] == expected["value"]
            for o in outputs
        )
        if not found:
            details.append(f"MISSING: {expected}")

    for category, substr in expectations.get("must_not", []):
        violation = any(
            o["category"] == category and (not substr or substr in o["value"])
            for o in outputs
        )
        if violation:
            details.append(f"MUST_NOT violated: {category}/{substr}")

    if not expectations.get("expect_signals") and outputs:
        details.append(f"FABRICATED: {len(outputs)} signals from no-signal event")

    passed = not details
    return Feedback(value=passed, rationale="; ".join(details) if details else "pass")


@scorer
def memory_manager_correctness(outputs: list[dict], expectations: dict) -> Feedback:
    """Expected ops present, forbidden ops absent."""
    details = []

    expect_op = expectations.get("expect_op")
    if expect_op:
        found = any(_matches_op(op, expect_op) for op in outputs)
        if not found:
            details.append(f"MISSING op: {expect_op}")

    for expected in expectations.get("expect_ops", []):
        found = any(_matches_op(op, expected) for op in outputs)
        if not found:
            details.append(f"MISSING op: {expected}")

    expect_any_of = expectations.get("expect_op_any_of", [])
    if expect_any_of:
        found = any(
            any(_matches_op(op, exp) for op in outputs) for exp in expect_any_of
        )
        if not found:
            details.append(f"NONE matched: {expect_any_of}")

    for forbidden in expectations.get("must_not_op", []):
        if any(_matches_op(op, forbidden) for op in outputs):
            details.append(f"FORBIDDEN op found: {forbidden}")

    passed = not details
    return Feedback(value=passed, rationale="; ".join(details) if details else "pass")


# ── Runners ──────────────────────────────────────────────────────────────────


def _label_run(run_id: str, name: str, tags: dict) -> None:
    client = mlflow.MlflowClient()
    client.set_tag(run_id, "mlflow.runName", name)
    for k, v in tags.items():
        client.set_tag(run_id, k, v)


def run_extractor_eval(cases: list[dict], set_name: str) -> float:
    dataset = [extractor_case_to_row(c) for c in cases]
    results = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=extractor_predict_fn,
        scorers=[extractor_correctness],
    )
    _label_run(results.run_id, f"extractor-eval-{set_name}", {"agent": "extractor", "set": set_name})
    return results.metrics.get("extractor_correctness/mean", 0.0)


def run_memory_manager_eval(cases: list[dict], set_name: str) -> float:
    dataset = [memory_manager_case_to_row(c) for c in cases]
    results = mlflow.genai.evaluate(
        data=dataset,
        predict_fn=memory_manager_predict_fn,
        scorers=[memory_manager_correctness],
    )
    _label_run(results.run_id, f"memory-manager-eval-{set_name}", {"agent": "memory_manager", "set": set_name})
    return results.metrics.get("memory_manager_correctness/mean", 0.0)


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    ext_scores = [
        run_extractor_eval(EXTRACTOR_DEV, "dev"),
        run_extractor_eval(EXTRACTOR_HELDOUT, "heldout"),
        run_extractor_eval(EXTRACTOR_ZH, "zh"),
    ]
    print(f"extractor    mean_correctness={sum(ext_scores) / len(ext_scores):.0%}")

    mm_scores = [
        run_memory_manager_eval(MEMORY_MANAGER_DEV, "dev"),
        run_memory_manager_eval(MEMORY_MANAGER_HELDOUT, "heldout"),
        run_memory_manager_eval(MEMORY_MANAGER_ZH, "zh"),
    ]
    print(f"memory_manager  mean_correctness={sum(mm_scores) / len(mm_scores):.0%}")


if __name__ == "__main__":
    main()
