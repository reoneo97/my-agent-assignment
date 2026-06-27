"""
Loop-level eval harness.

Runs a full simulated operator session through the hot-path pipeline, logging
every turn as a nested MLflow run. At the end computes deterministic trait
inference metrics (precision / recall / F1) against the persona ground truth.

  - Trait inference precision/recall/F1 vs persona ground truth
  - Per-turn: signal count, op count, profile size
  - Token usage: captured automatically via MLflow autolog (no extra code)

Usage:
  uv run python -m eval.run_loop_evals --operator-id op-demo-01 --n 10
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from ola.telemetry import setup_tracing
setup_tracing()

import mlflow  # noqa: E402


async def run_eval(operator_id: str, n: int, db_path: str) -> None:
    from sim.persona import get_eval_ground_truth, get_next_interaction
    from ola.pipeline import process_interaction
    from ola.memory.store import get_or_create_session, get_profile
    from eval.metrics import compute_inference_report

    gt = get_eval_ground_truth(operator_id)
    if gt is None:
        print(f"No ground truth for {operator_id}")
        return

    all_traits = {**gt["early_traits"], **gt.get("drifted_traits", {})}

    with mlflow.start_run(run_name="full-loop-eval", tags={"operator_id": operator_id, "n": str(n)}) as run:
        mlflow.log_params({"operator_id": operator_id, "n_interactions": n})

        session_id = get_or_create_session(operator_id, db_path=db_path)

        for i in range(n):
            interaction = await get_next_interaction(operator_id)

            with mlflow.start_run(run_name=f"turn-{i+1}", nested=True):
                signals, ops, profile, reply = await process_interaction(
                    interaction, session_id=session_id, db_path=db_path
                )
                mlflow.log_metrics({
                    "n_signals": len(signals),
                    "n_ops": len(ops),
                    "profile_size": len(profile.active_items),
                })
                mlflow.log_text(reply, f"reply_turn_{i+1}.txt")

        final_profile = get_profile(operator_id, db_path=db_path)
        report = compute_inference_report(operator_id, all_traits, final_profile.active_items)

        mlflow.log_metrics({
            "trait_precision": report.precision,
            "trait_recall": report.recall,
            "trait_f1": report.f1,
            "traits_matched": len(report.matched),
            "traits_missed": len(report.missed),
            "traits_spurious": len(report.spurious),
        })
        mlflow.log_dict(report.as_dict(), "inference_report.json")
        mlflow.log_dict(
            {
                "matched": [vars(m) for m in report.matched],
                "missed": [vars(m) for m in report.missed],
                "spurious": report.spurious,
            },
            "trait_details.json",
        )

        print(f"\n── Eval complete (run: {run.info.run_id[:8]}) ──")
        print(f"  Trait inference:  P={report.precision:.2f}  R={report.recall:.2f}  F1={report.f1:.2f}")
        print(f"  MLflow UI:        make mlflow-ui")


def main() -> None:
    parser = argparse.ArgumentParser(description="OLA loop eval harness")
    parser.add_argument("--operator-id", default="op-demo-01")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--db", default=None, help="SQLite path (default: temp db)")
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    asyncio.run(run_eval(args.operator_id, args.n, db_path))


if __name__ == "__main__":
    main()
