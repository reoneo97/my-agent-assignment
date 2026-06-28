"""
Loop-level eval harness.

Runs a full simulated operator session through the hot-path pipeline, then
evaluates on TWO dimensions:

1. STRUCTURAL (fast, lexical, judge-free):
   - Trait inference precision/recall/F1 vs persona ground truth
   - Per-turn: signal count, op count, profile size
   - Token usage: captured automatically via MLflow autolog

2. CONVERSATIONAL (richer, judge-based, run at milestones):
   - ConversationCompleteness: did the assistant resolve the operator's issue?
   - UserFrustration: did the operator become frustrated?
   - PersonalizationCompliance: did the assistant respect the learned profile?
   - EscalationAppropriateness: did the assistant match guidance to alarm complexity?

The structural eval is the tight inner loop (every iteration). The conversation
eval is the outer loop (milestones only — costs tokens). Use --skip-conversation
to run structural-only during rapid iteration.

Usage:
  uv run python -m eval.run_loop_evals --operator-id op-demo-01 --n 10
  uv run python -m eval.run_loop_evals --operator-id op-demo-01 --n 10 --skip-conversation
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

# MLflow's built-in judges use the OpenAI SDK and require OPENAI_API_KEY /
# OPENAI_BASE_URL. Map our provider env vars so judges route through OpenRouter.
# MLFLOW_GENAI_JUDGE_DEFAULT_MODEL sets the model used by make_judge / built-ins.
import os as _os
if not _os.environ.get("OPENAI_API_KEY"):
    _os.environ["OPENAI_API_KEY"] = _os.environ.get("MODEL_API_KEY", "")
if not _os.environ.get("OPENAI_BASE_URL"):
    _os.environ["OPENAI_BASE_URL"] = _os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
if not _os.environ.get("MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"):
    # MLflow judges use structured tool-calling internally — needs a model that
    # reliably supports function calling. Default to gpt-4o-mini (cheap, stable)
    # rather than STRONG_MODEL_NAME which may not support MLflow's judge format.
    # Override by setting MLFLOW_GENAI_JUDGE_DEFAULT_MODEL=openai:/your-model in .env
    _os.environ["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"] = "openai:/openai/gpt-4o-mini"

from ola.telemetry import setup_tracing

setup_tracing()

import mlflow  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Custom conversation judges (domain-specific)
# ─────────────────────────────────────────────────────────────────────────────


def _build_conversation_scorers():
    """Build the conversation-level scorers. Separated so import cost is paid
    only when conversation eval is enabled."""
    from mlflow.genai.scorers import ConversationCompleteness
    from mlflow.genai.judges import make_judge
    from typing import Literal

    personalization_compliance = make_judge(
        name="personalization_compliance",
        instructions=(
            "The assistant is a manufacturing operator learning assistant that "
            "builds a profile of each operator's preferences over time. "
            "Operator input: {{ inputs }}. Assistant response: {{ outputs }}. "
            "Evaluate whether the response personalizes to the operator — using "
            "the right instruction modality (visual/text/human guidance), appropriate "
            "verbosity for their confidence level, asking confirmation questions "
            "for uncertain beliefs rather than assuming, and reducing scaffolding "
            "only when confidence is established. "
            "Rate compliance with personalization."
        ),
        feedback_value_type=Literal[
            "fully_compliant", "partially_compliant", "non_compliant"
        ],
    )

    response_conciseness = make_judge(
        name="response_conciseness",
        instructions=(
            "This is a manufacturing shopfloor assistant helping an operator "
            "with machine alarms. The operator needs fast, clear, actionable "
            "answers — not lengthy explanations that are hard to interpret on "
            "the shopfloor. Operator input: {{ inputs }}. "
            "Assistant response: {{ outputs }}. "
            "Evaluate whether the response is concise and direct: does it get "
            "to the point immediately, avoid unnecessary preamble or summaries "
            "of what the operator just said, and keep instructions short enough "
            "that a busy operator can act on them immediately? "
            "A good response gives the essential next step first and only adds "
            "detail if strictly necessary. "
            "Rate the conciseness of the response."
        ),
        feedback_value_type=Literal["concise", "acceptable", "too_verbose"],
    )

    response_quality = make_judge(
        name="response_quality",
        instructions=(
            "The assistant is helping a manufacturing operator resolve machine "
            "alarms. Operator input: {{ inputs }}. Assistant response: {{ outputs }}. "
            "Evaluate the response quality: is it factually grounded (referencing "
            "real procedures/alarm codes rather than inventing them), concise "
            "(not over-explaining to a confident operator), and actionable "
            "(giving clear next steps rather than vague advice)? "
            "Rate the response quality."
        ),
        feedback_value_type=Literal["high", "medium", "low"],
    )

    return [
        ConversationCompleteness(),
        personalization_compliance,
        response_conciseness,
        response_quality,
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Reset to baseline
# ─────────────────────────────────────────────────────────────────────────────


def reset_to_baseline(db_path: str) -> None:
    """Reset mutable state to post-bootstrap baseline.
    - SQL: fresh ephemeral DB (the db_path is already a temp file)
    - KG: delete learned/discovered edges, keep Wave 1 seed
    """
    from ola.memory.store import _connect

    _connect(db_path).close()  # creates and initialises the schema

    try:
        from ola.kg.client import get_driver

        driver = get_driver()
        with driver.session() as session:
            # Delete only learned operator-belief edges, keep domain seed
            session.run("""
                MATCH (:Operator)-[r:PREFERS|CONFIDENT_WITH|STRUGGLES_WITH]->()
                DELETE r
            """)
            session.run("""
                MATCH ()-[r:ALSO_RESOLVED_BY]->()
                WHERE r.source = 'DISCOVERED'
                DELETE r
            """)
        print("  KG: learned edges cleared, seed preserved")
    except Exception as e:
        print(f"  KG reset skipped: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation eval (the outer loop — milestone only)
# ─────────────────────────────────────────────────────────────────────────────


def run_conversation_eval(session_ids: list[str], experiment_id: str) -> dict:
    """Pull responder traces across all eval sessions and run conversation scorers."""
    scorers = _build_conversation_scorers()

    traces = []
    for sid in session_ids:
        batch = mlflow.search_traces(
            experiment_ids=[experiment_id],
            filter_string=f"metadata.`mlflow.trace.session` = '{sid}'",
            return_type="list",
        )
        traces.extend(batch)

    # Keep only responder traces — those have operator input → assistant output.
    # Extractor/memory_manager traces are internal and lack meaningful I/O for judges.
    traces = [
        t for t in traces
        if t.info.tags.get("mlflow.traceName") == "responder"
    ]

    if not traces:
        print("  Conversation eval: no responder traces found for session — skipping")
        return {}

    print(f"  Conversation eval: scoring {len(traces)} responder traces...")

    results = mlflow.genai.evaluate(
        data=traces,
        scorers=scorers,
    )

    return {k: float(v) for k, v in results.metrics.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Main eval loop
# ─────────────────────────────────────────────────────────────────────────────


async def run_eval(
    operator_id: str,
    n: int,
    db_path: str,
    skip_conversation: bool = False,
) -> None:
    from sim.persona import get_eval_ground_truth, get_next_interaction
    from ola.pipeline import process_interaction
    from ola.memory.store import get_or_create_session, get_profile
    from eval.metrics import compute_inference_report

    # Reset to clean baseline before each persona
    reset_to_baseline(db_path)

    gt = get_eval_ground_truth(operator_id)
    if gt is None:
        print(f"No ground truth for {operator_id}")
        return

    all_traits = {**gt["early_traits"], **gt.get("drifted_traits", {})}

    run_tags = {
        "operator_id": operator_id,
        "n": str(n),
        "eval_type": "structural" if skip_conversation else "structural+conversation",
    }

    with mlflow.start_run(run_name=f"loop-eval-{operator_id}", tags=run_tags) as run:
        mlflow.log_params({"operator_id": operator_id, "n_interactions": n})

        experiment_id = run.info.experiment_id
        session_ids: list[str] = []

        # One session per interaction — matches the design ("one session per issue
        # resolution") and gives N separate conversations in the MLflow traces UI.
        client = mlflow.MlflowClient()
        for _ in range(n):
            session_id = get_or_create_session(operator_id, db_path=db_path)
            session_ids.append(session_id)
            interaction = await get_next_interaction(operator_id)
            await process_interaction(interaction, session_id=session_id, db_path=db_path)
            # Close the session so the next iteration opens a fresh one.
            from ola.memory.store import close_session
            close_session(session_id, status="abandoned", db_path=db_path)

        # Retroactively link all session traces to this MLflow run (async context
        # doesn't inherit the thread-local start_run context).
        for sid in session_ids:
            session_traces = mlflow.search_traces(
                experiment_ids=[experiment_id],
                filter_string=f"metadata.`mlflow.trace.session` = '{sid}'",
                return_type="list",
            )
            for t in session_traces:
                client.set_trace_tag(t.info.request_id, "mlflow.sourceRunId", run.info.run_id)

        # ── Structural eval ───────────────────────────────────────────────
        final_profile = get_profile(operator_id, db_path=db_path)
        report = compute_inference_report(operator_id, all_traits, final_profile.active_items)

        mlflow.log_metrics(
            {
                "trait_precision": report.precision,
                "trait_recall": report.recall,
                "trait_f1": report.f1,
                "traits_matched": len(report.matched),
                "traits_missed": len(report.missed),
                "traits_spurious": len(report.spurious),
            }
        )
        mlflow.log_dict(report.as_dict(), "inference_report.json")
        mlflow.log_dict(
            {
                "matched": [vars(m) for m in report.matched],
                "missed": [vars(m) for m in report.missed],
                "spurious": report.spurious,
            },
            "trait_details.json",
        )

        print(f"\n── Structural eval ──")
        print(f"  Trait inference:  P={report.precision:.2f}  R={report.recall:.2f}  F1={report.f1:.2f}")
        print(f"  Matched: {[m.trait_key for m in report.matched]}")
        print(f"  Missed:  {[m.trait_key for m in report.missed]}")
        print(f"  Spurious: {report.spurious}")

        # ── Conversation eval (rich, milestone only) ──────────────────────
        if not skip_conversation:
            print(f"\n── Conversation eval ──")
            conv_scores = run_conversation_eval(session_ids, experiment_id)
            if conv_scores:
                mlflow.log_metrics(conv_scores)
                for k, v in conv_scores.items():
                    print(f"  {k}: {v}")
            else:
                print("  No conversation scores returned")
        else:
            print("\n  Conversation eval: skipped (--skip-conversation)")

        print(f"\n── Eval complete (run: {run.info.run_id[:8]}) ──")


# ─────────────────────────────────────────────────────────────────────────────
# Multi-persona batch
# ─────────────────────────────────────────────────────────────────────────────


async def run_batch_eval(
    operator_ids: list[str],
    n: int,
    skip_conversation: bool = False,
) -> None:
    """Run eval for multiple personas, each with a fresh baseline."""
    for op_id in operator_ids:
        print(f"\n{'='*60}")
        print(f"  Persona: {op_id}")
        print(f"{'='*60}")

        # Each persona gets a fresh ephemeral DB
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            await run_eval(op_id, n, db_path, skip_conversation)
        finally:
            # Clean up temp DB
            try:
                os.unlink(db_path)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="OLA loop eval harness")
    parser.add_argument(
        "--operator-id",
        default=None,
        help="Single operator ID to eval (default: all eval personas)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all eval personas",
    )
    parser.add_argument("--n", type=int, default=10, help="Interactions per persona")
    parser.add_argument(
        "--db", default=None, help="SQLite path (default: temp db per persona)"
    )
    parser.add_argument(
        "--skip-conversation",
        action="store_true",
        help="Skip conversation-level judges (faster, structural metrics only)",
    )
    args = parser.parse_args()

    if args.all or args.operator_id is None:
        # Run all eval personas
        from sim.persona import get_eval_operator_ids

        operator_ids = get_eval_operator_ids()
        print(f"Running batch eval for {len(operator_ids)} personas: {operator_ids}")
        asyncio.run(run_batch_eval(operator_ids, args.n, args.skip_conversation))
    else:
        # Single persona
        if args.db:
            db_path = args.db
        else:
            fd, db_path = tempfile.mkstemp(suffix=".db")
            os.close(fd)
        asyncio.run(run_eval(args.operator_id, args.n, db_path, args.skip_conversation))


if __name__ == "__main__":
    main()
