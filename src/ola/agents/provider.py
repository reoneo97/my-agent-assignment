from __future__ import annotations

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ola.config import FAST_MODEL_NAME, MODEL_API_KEY, MODEL_BASE_URL, STRONG_MODEL_NAME


def _provider() -> OpenAIProvider:
    return OpenAIProvider(base_url=MODEL_BASE_URL, api_key=MODEL_API_KEY)


def make_model() -> OpenAIModel:
    """Fast model — hot path (Extractor, Memory Manager, Responder)."""
    return OpenAIModel(FAST_MODEL_NAME, provider=_provider())


def make_fast_model() -> OpenAIModel:
    return make_model()


def make_strong_model() -> OpenAIModel:
    """Strong model — Reviewer, Manual Extractor (run rarely, quality matters)."""
    return OpenAIModel(STRONG_MODEL_NAME, provider=_provider())
