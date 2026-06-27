from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# OpenRouter endpoint — override via env for local/alternative providers
_BASE_URL = os.environ.get("MODEL_BASE_URL", "https://openrouter.ai/api/v1")

# A non-empty placeholder lets agent construction succeed at import time in
# test/CI contexts that never make a real call; actual calls still fail normally.
_API_KEY = os.environ.get("MODEL_API_KEY") or "sk-no-key-configured"

# Hot path (Extractor, Memory Manager, Responder) — fast + cheap
FAST_MODEL = os.environ.get("FAST_MODEL_NAME", "deepseek/deepseek-v4-flash")

# Slow path (Reviewer, Manual Extractor) — stronger reasoning, runs rarely
STRONG_MODEL = os.environ.get("STRONG_MODEL_NAME", "minimax/minimax-m2.7")


def _provider() -> OpenAIProvider:
    return OpenAIProvider(base_url=_BASE_URL, api_key=_API_KEY)


def make_model() -> OpenAIChatModel:
    """Fast model — hot path."""
    return OpenAIChatModel(FAST_MODEL, provider=_provider())


def make_fast_model() -> OpenAIChatModel:
    return make_model()


def make_strong_model() -> OpenAIChatModel:
    """Strong model — Reviewer, Manual Extractor."""
    return OpenAIChatModel(STRONG_MODEL, provider=_provider())
