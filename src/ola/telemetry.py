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

import logging
import traceback
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger("ola.agents")

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


@asynccontextmanager
async def agent_span(name: str):
    """Async context manager that wraps an agent call in a named MLflow span.

    The autolog Agent.run span becomes a child of this span, making each agent
    clearly identifiable in the trace tree by name.

    Usage::

        async with agent_span("extractor"):
            result = await _agent.run(prompt)
    """
    try:
        import mlflow
        with mlflow.start_span(name=name) as span:
            span.set_attribute("agent.name", name)
            yield span
    except ImportError:
        yield None
    except Exception:
        yield None


def log_agent_failure(
    agent_name: str,
    exc: Exception,
    context: dict[str, Any],
    prompt: str | None = None,
) -> None:
    """Log a structured-output agent failure to both the Python logger and the
    active MLflow span (if tracing is active).

    Parameters
    ----------
    agent_name:
        Short label for the failing agent, e.g. "extractor" or "memory_manager".
    exc:
        The caught exception.
    context:
        Dict of key/value pairs describing the call site — operator_id, event_id,
        alarm_code, etc.  All values must be JSON-serialisable primitives.
    prompt:
        The rendered prompt that was sent to the model, if available.  Logged as
        a span attribute so it can be inspected alongside the raw response body.
    """
    raw_body: str | None = getattr(exc, "body", None)
    error_type = type(exc).__name__
    error_msg = str(exc)

    # ── Python logger (always) ──────────────────────────────────────────────
    logger.error(
        "[%s] structured-output failure after retries exhausted | "
        "error_type=%s | context=%s | error=%s%s",
        agent_name,
        error_type,
        context,
        error_msg,
        f" | raw_body={raw_body}" if raw_body else "",
    )
    logger.debug("[%s] traceback:\n%s", agent_name, traceback.format_exc())

    # ── MLflow active span (if tracing is running) ──────────────────────────
    try:
        import mlflow

        span = mlflow.get_current_active_span()
        if span is not None:
            span.set_attribute(f"{agent_name}.failure", True)
            span.set_attribute(f"{agent_name}.error_type", error_type)
            span.set_attribute(f"{agent_name}.error_message", error_msg)
            for k, v in context.items():
                span.set_attribute(f"{agent_name}.ctx.{k}", str(v))
            if raw_body:
                span.set_attribute(f"{agent_name}.raw_response_body", raw_body)
            if prompt:
                span.set_attribute(f"{agent_name}.prompt_sent", prompt[:4000])
    except Exception:
        # Never let telemetry crash the pipeline.
        pass
