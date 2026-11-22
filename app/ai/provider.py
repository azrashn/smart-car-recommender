"""LLM provider interface and factory (M4, T30).

The rest of the application talks only to ``LLMProvider``; no other module
imports the Gemini SDK directly. Callers must treat any ``LLMError`` as
"AI unavailable" and use their rule/template fallback (NFR-02).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.ai.config import AISettings, load_ai_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base error for the AI layer. Messages never contain API keys."""


class LLMUnavailableError(LLMError):
    """AI is disabled or not configured; callers should use the fallback."""


class LLMProviderError(LLMError):
    """The provider was called but failed (network, timeout, quota, bad reply)."""


class LLMProvider(ABC):
    """Provider-agnostic text generation interface."""

    name: str = "base"

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True when ``generate`` can actually reach a model."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str:
        """Return the raw model text for ``prompt``.

        Raises ``LLMUnavailableError`` or ``LLMProviderError`` on failure.
        Output is untrusted: callers validate it (e.g. with Pydantic).
        """


def create_provider(settings: AISettings) -> LLMProvider:
    """Build the provider described by ``settings``.

    Any misconfiguration (missing key, missing SDK) degrades to ``NoneProvider``
    with a warning instead of crashing the application.
    """
    from app.ai.none import NoneProvider

    if settings.provider == "gemini":
        if not settings.gemini_api_key:
            logger.warning(
                "AI_PROVIDER=gemini but GEMINI_API_KEY is missing; AI disabled."
            )
            return NoneProvider()
        try:
            from app.ai.gemini import GeminiProvider

            return GeminiProvider(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.timeout_seconds,
            )
        except LLMError as exc:
            logger.warning(
                "Gemini provider could not be created (%s); AI disabled.", exc
            )
            return NoneProvider()

    return NoneProvider()


_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the process-wide provider, created lazily from the environment."""
    global _provider
    if _provider is None:
        _provider = create_provider(load_ai_settings())
    return _provider


def reset_provider() -> None:
    """Forget the cached provider (used by tests or after config changes)."""
    global _provider
    _provider = None
