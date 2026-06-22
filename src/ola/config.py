from __future__ import annotations

import os

# Confidence tier thresholds
TENTATIVE_THRESHOLD = 3  # evidence_count < this => tentative
ESTABLISHED_THRESHOLD = 3  # evidence_count >= this => established

# SQLite DB path
DB_PATH = os.environ.get("OLA_DB_PATH", "ola.db")

# LLM provider (read at import time so agents get consistent values)
MODEL_NAME = os.environ.get("MODEL_NAME", "meta-llama/llama-3.3-70b-instruct")
MODEL_BASE_URL = os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
