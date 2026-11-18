"""NoneProvider: the default provider when AI is disabled (AI_PROVIDER=none)."""

from __future__ import annotations

from app.ai.provider import LLMProvider, LLMUnavailableError


class NoneProvider(LLMProvider):
    """Never calls a model; signals callers to use their rule/template fallback."""

    name = "none"

    @property
    def is_available(self) -> bool:
        return False

    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str:
        raise LLMUnavailableError("AI provider is disabled (AI_PROVIDER=none).")
