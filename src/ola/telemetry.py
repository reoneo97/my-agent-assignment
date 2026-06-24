"""
MLflow tracing setup — call setup_tracing() once at process start.

mlflow.pydantic_ai.autolog() instruments every Agent.run() call as an MLflow
span, capturing inputs, outputs, and token usage (MLflow >= 3.2.0) without
any changes to agent code. On by default; disable with MLFLOW_ENABLED=false.

Token usage appears in:
  - trace summary: mlflow.get_trace(trace_id).info.token_usage
  - per-span attributes: span.get_attribute("llm.usage.*")

This gives the cost/latency story for free — relevant to the production-
economics point about agent token overhead vs single-call baselines.
"""

from __future__ import annotations

_setup_done = False


def setup_tracing() -> None:
    """Idempotent — safe to call from multiple entry points."""
    global _setup_done
    if _setup_done:
        return

    from ola.config import MLFLOW_ENABLED, MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI

    if not MLFLOW_ENABLED:
        _setup_done = True
        return

    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        mlflow.pydantic_ai.autolog()
        print(f"  MLflow tracing enabled → {MLFLOW_TRACKING_URI} / {MLFLOW_EXPERIMENT}")
    except Exception as exc:
        print(f"  MLflow tracing unavailable: {exc}")

    _setup_done = True
