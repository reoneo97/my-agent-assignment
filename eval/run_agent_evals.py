"""
Agent-level eval harness.

Runs structured-output evals against individual agents (Extractor, Memory Manager)
using hand-authored cases with deterministic scoring — no LLM judge needed.

Three sets per agent:
  dev     — tune against these
  heldout — report final numbers here (don't tune to it)
  zh      — Mandarin input robustness (canonical enum values must not translate)

Usage:
  uv run python -m eval.run_agent_evals
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import mlflow  # noqa: E402

from ola.telemetry import setup_tracing
from ola.agents.extractor import extract_signals
from ola.agents.memory_manager import decide_operations
from ola.domain.events import OperatorInteraction
from ola.domain.memory import MemoryItem
from eval.eval_sets import (
    EXTRACTOR_DEV,
    EXTRACTOR_HELDOUT,
    EXTRACTOR_ZH,
    MEMORY_MANAGER_DEV,
    MEMORY_MANAGER_HELDOUT,
    MEMORY_MANAGER_ZH,
)

setup_tracing()


# ── Scoring helpers ──────────────────────────────────────────────────────────


def score_extractor(produced_signals, case):
    """Check expected signals present, must_not signals absent."""
    results = {"pass": True, "details": []}

    for expected in case.get("expect_signals", []):
        found = any(
            s.category.value == expected["category"] and s.value == expected["value"]
            for s in produced_signals
        )
        if not found:
            results["pass"] = False
            results["details"].append(f"MISSING: {expected}")

    for category, substr in case.get("must_not", []):
        violation = any(
            s.category.value == category and (not substr or substr in s.value)
            for s in produced_signals
        )
        if violation:
            results["pass"] = False
            results["details"].append(f"MUST_NOT violated: {category}/{substr}")

    # Empty expected + any signals produced = fabrication fail
    if not case.get("expect_signals") and produced_signals:
        results["pass"] = False
        results["details"].append(
            f"FABRICATED: {len(produced_signals)} signals from no-signal event"
        )

    return results


def score_memory_manager(produced_ops, case):
    """Check expected ops present, forbidden ops absent."""
    results = {"pass": True, "details": []}

    if "expect_op" in case:
        found = any(matches_op(op, case["expect_op"]) for op in produced_ops)
        if not found:
            results["pass"] = False
            results["details"].append(f"MISSING op: {case['expect_op']}")

    for expected in case.get("expect_ops", []):
        found = any(matches_op(op, expected) for op in produced_ops)
        if not found:
            results["pass"] = False
            results["details"].append(f"MISSING op: {expected}")

    if "expect_op_any_of" in case:
        found = any(
            any(matches_op(op, exp) for op in produced_ops)
            for exp in case["expect_op_any_of"]
        )
        if not found:
            results["pass"] = False
            results["details"].append(f"NONE matched: {case['expect_op_any_of']}")

    for forbidden in case.get("must_not_op", []):
        if any(matches_op(op, forbidden) for op in produced_ops):
            results["pass"] = False
            results["details"].append(f"FORBIDDEN op found: {forbidden}")

    return results


def matches_op(produced, expected):
    """Match a produced op against an expected op spec on all specified fields."""
    if produced.op_type.upper() != expected.get("op_type", "").upper():
        return False
    if "target_item_id" in expected and produced.target_item_id != expected["target_item_id"]:
        return False
    if "value" in expected and produced.value != expected["value"]:
        return False
    return True


# ── Runners ──────────────────────────────────────────────────────────────────


async def run_extractor_eval(cases, set_name):
    passed = 0
    for case in cases:
        event = OperatorInteraction(
            id=case["event"].get("source_event_id", "eval-event"),
            operator_id="eval-operator",
            timestamp="2026-06-27T00:00:00Z",
            event_type=case["event"]["event_type"],
            alarm_code=case["event"].get("alarm_code"),
            content=case["event"]["content"],
            outcome=case["event"].get("outcome"),
            requested_modality=case["event"].get("requested_modality"),
        )
        signals = await extract_signals(event)
        result = score_extractor(signals, case)

        if result["pass"]:
            passed += 1
            print(f"  ✓ {case['id']}: {case['tests']}")
        else:
            print(f"  ✗ {case['id']}: {case['tests']}")
            for d in result["details"]:
                print(f"      {d}")

    total = len(cases)
    accuracy = passed / total if total else 0
    print(f"\n  {set_name}: {passed}/{total} ({accuracy:.0%})\n")
    return accuracy


async def run_memory_manager_eval(cases, set_name):
    from ola.domain.signals import BehaviouralSignal, TraitCategory

    passed = 0
    for case in cases:
        signals = [
            BehaviouralSignal(
                category=TraitCategory(s["category"]),
                value=s["value"],
                observation=s["observation"],
                source_event_id="eval-event",
            )
            for s in case["signals"]
        ]
        current_items = [
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
            for item in case.get("current_items", [])
        ]
        ops = await decide_operations(
            signals=signals,
            current_items=current_items,
            operator_id="eval-operator",
            source_event_id="eval-event",
        )
        result = score_memory_manager(ops, case)

        if result["pass"]:
            passed += 1
            print(f"  ✓ {case['id']}: {case['tests']}")
        else:
            print(f"  ✗ {case['id']}: {case['tests']}")
            for d in result["details"]:
                print(f"      {d}")

    total = len(cases)
    accuracy = passed / total if total else 0
    print(f"\n  {set_name}: {passed}/{total} ({accuracy:.0%})\n")
    return accuracy


# ── Main ─────────────────────────────────────────────────────────────────────


async def main():
    print("=== Extractor ===")
    with mlflow.start_run(run_name="extractor-eval", tags={"agent": "extractor"}):
        print("--- dev ---")
        ext_dev = await run_extractor_eval(EXTRACTOR_DEV, "extractor_dev")
        print("--- heldout ---")
        ext_held = await run_extractor_eval(EXTRACTOR_HELDOUT, "extractor_heldout")
        print("--- zh ---")
        ext_zh = await run_extractor_eval(EXTRACTOR_ZH, "extractor_zh")
        mlflow.log_metric("dev_accuracy", ext_dev)
        mlflow.log_metric("heldout_accuracy", ext_held)
        mlflow.log_metric("zh_accuracy", ext_zh)
    print(f"  dev={ext_dev:.0%}  heldout={ext_held:.0%}  zh={ext_zh:.0%}\n")

    print("=== Memory Manager ===")
    with mlflow.start_run(run_name="memory-manager-eval", tags={"agent": "memory_manager"}):
        print("--- dev ---")
        mm_dev = await run_memory_manager_eval(MEMORY_MANAGER_DEV, "mm_dev")
        print("--- heldout ---")
        mm_held = await run_memory_manager_eval(MEMORY_MANAGER_HELDOUT, "mm_heldout")
        print("--- zh ---")
        mm_zh = await run_memory_manager_eval(MEMORY_MANAGER_ZH, "mm_zh")
        mlflow.log_metric("dev_accuracy", mm_dev)
        mlflow.log_metric("heldout_accuracy", mm_held)
        mlflow.log_metric("zh_accuracy", mm_zh)
    print(f"  dev={mm_dev:.0%}  heldout={mm_held:.0%}  zh={mm_zh:.0%}")


if __name__ == "__main__":
    asyncio.run(main())
