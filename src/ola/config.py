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


# Neo4j connection
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# MLflow — tracing + eval
MLFLOW_ENABLED = os.environ.get("MLFLOW_ENABLED", "true").lower() == "true"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "mlruns")
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "ola-dev")
