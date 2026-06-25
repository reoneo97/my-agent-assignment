from __future__ import annotations

import os

# Confidence tier thresholds
TENTATIVE_THRESHOLD = 3  # evidence_count < this => tentative
ESTABLISHED_THRESHOLD = 3  # evidence_count >= this => established

# SQLite DB path
DB_PATH = os.environ.get("OLA_DB_PATH", "ola.db")

# Session lifecycle
SESSION_INACTIVITY_TIMEOUT_MINUTES = int(os.environ.get("SESSION_INACTIVITY_TIMEOUT_MINUTES", "30"))

# Basic auth for the app (API + UI) — disabled unless both are set.
BASIC_AUTH_USER = os.environ.get("BASIC_AUTH_USER", "")
BASIC_AUTH_PASSWORD = os.environ.get("BASIC_AUTH_PASSWORD", "")

# LLM provider — fast model for hot path, strong model for Reviewer / Manual Extractor
MODEL_BASE_URL = os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
# Agent objects are constructed eagerly at module import time (see agents/*.py),
# which builds an AsyncOpenAI client that raises if api_key is empty/missing —
# even in contexts (pure unit tests, CI without secrets) that never make a real
# call. A non-empty placeholder lets that construction succeed; a real call
# without a real key still fails normally, just at call time instead of import time.
MODEL_API_KEY = os.environ.get("MODEL_API_KEY") or "sk-no-key-configured"

FAST_MODEL_NAME = os.environ.get(
    "FAST_MODEL_NAME",
    os.environ.get("MODEL_NAME", "meta-llama/llama-3.3-70b-instruct"),
)
STRONG_MODEL_NAME = os.environ.get(
    "STRONG_MODEL_NAME",
    os.environ.get("MODEL_NAME", "meta-llama/llama-3.3-70b-instruct"),
)
# Legacy alias kept for backward compat
MODEL_NAME = FAST_MODEL_NAME

# Neo4j connection
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# MLflow — tracing + eval
MLFLOW_ENABLED = os.environ.get("MLFLOW_ENABLED", "true").lower() == "true"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "mlruns")
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "ola-dev")
