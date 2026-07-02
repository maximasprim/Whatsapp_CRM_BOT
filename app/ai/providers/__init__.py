from __future__ import annotations

from functools import lru_cache

from app.ai.providers.base import AIProvider
from app.core.config import settings


@lru_cache
def get_ai_provider() -> AIProvider:
    """Return the active AI provider based on AI_PROVIDER env var."""
    if settings.AI_PROVIDER == "gemini":
        from app.ai.providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    # Default to OpenAI
    from app.ai.providers.openai_provider import OpenAIProvider
    return OpenAIProvider()


# FastAPI dependency
def ai_provider_dep() -> AIProvider:
    return get_ai_provider()
