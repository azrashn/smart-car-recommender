"""AutoMatch M4 AI layer: optional LLM provider behind a provider interface."""

from app.ai.config import AISettings, load_ai_settings
from app.ai.none import NoneProvider
from app.ai.provider import (
    LLMError,
    LLMProvider,
    LLMProviderError,
    LLMUnavailableError,
    create_provider,
    get_provider,
    reset_provider,
)

__all__ = [
    "AISettings",
    "LLMError",
    "LLMProvider",
    "LLMProviderError",
    "LLMUnavailableError",
    "NoneProvider",
    "create_provider",
    "get_provider",
    "load_ai_settings",
    "reset_provider",
]
