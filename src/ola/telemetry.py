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
from functools import wraps
from typing import Any

import mlflow

from ola.config import MLFLOW_ENABLED, MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI

logger = logging.getLogger("ola.agents")

_setup_done = False


def setup_tracing() -> None:
    """Idempotent — safe to call from multiple entry points."""
    global _setup_done
    if _setup_done:
        return

    if not MLFLOW_ENABLED:
        _setup_done = True
        return

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    mlflow.pydantic_ai.autolog()
    print(f"  MLflow tracing enabled → {MLFLOW_TRACKING_URI} / {MLFLOW_EXPERIMENT}")

    _setup_done = True


def traced_interaction(fn):
    """Decorator function to trace session_id information to mlflow

    Args:
        fn (function): LLM Pipeline Call

    """
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        session_id = kwargs["session_id"]
        operator_id = kwargs["interaction"].operator_id
        with mlflow.tracing.context(session_id=session_id, user=operator_id):
            return await fn(*args, **kwargs)
    return wrapper


@asynccontextmanager
async def agent_span(name: str):
    with mlflow.start_span(name=name) as span:
        span.set_attribute("agent.name", name)
        yield span


def log_agent_failure(
    agent_name: str,
    exc: Exception,
    context: dict[str, Any],
    prompt: str | None = None,
) -> None:
    """Log a structured-output agent failure to both the Python logger and the
    active MLflow span."""
    raw_body: str | None = getattr(exc, "body", None)
    error_type = type(exc).__name__
    error_msg = str(exc)

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
