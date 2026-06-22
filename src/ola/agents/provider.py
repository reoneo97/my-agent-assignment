from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ola.config import MODEL_API_KEY, MODEL_BASE_URL, MODEL_NAME


def make_model() -> OpenAIModel:
    """Return a Pydantic AI model configured from environment variables."""
    provider = OpenAIProvider(base_url=MODEL_BASE_URL, api_key=MODEL_API_KEY)
    return OpenAIModel(MODEL_NAME, provider=provider)
