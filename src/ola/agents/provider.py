from __future__ import annotations

import os

from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings
from pydantic_ai.providers.openrouter import OpenRouterProvider

_API_KEY = os.environ.get("MODEL_API_KEY") or "sk-no-key-configured"

# Hot path (Extractor, Memory Manager, Responder) — fast + cheap, no reasoning
FAST_MODEL = os.environ.get("FAST_MODEL_NAME", "deepseek/deepseek-v4-flash")

# Slow path (Reviewer, Manual Extractor) — stronger reasoning, runs rarely
STRONG_MODEL = os.environ.get("STRONG_MODEL_NAME", "minimax/minimax-m2.7")

FAST_SETTINGS = OpenRouterModelSettings(openrouter_reasoning={"effort": "none"})
STRONG_SETTINGS = OpenRouterModelSettings(openrouter_reasoning={"effort": "high"})


def _provider() -> OpenRouterProvider:
    return OpenRouterProvider(api_key=_API_KEY)


def make_model() -> OpenRouterModel:
    """Fast model — hot path."""
    return OpenRouterModel(FAST_MODEL, provider=_provider())


def make_fast_model() -> OpenRouterModel:
    return make_model()


def make_strong_model() -> OpenRouterModel:
    """Strong model — Reviewer, Manual Extractor."""
    return OpenRouterModel(STRONG_MODEL, provider=_provider())
