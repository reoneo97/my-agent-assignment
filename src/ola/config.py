from __future__ import annotations

import os

# Confidence tier thresholds
TENTATIVE_THRESHOLD = 3  # evidence_count < this => tentative
ESTABLISHED_THRESHOLD = 3  # evidence_count >= this => established

# SQLite DB path
DB_PATH = os.environ.get("OLA_DB_PATH", "ola.db")

# LLM provider — fast model for hot path, strong model for Reviewer / Manual Extractor
MODEL_BASE_URL = os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")

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
