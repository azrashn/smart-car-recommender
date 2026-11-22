"""GeminiProvider: Google Gemini via the ``google-genai`` SDK (optional)."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.provider import LLMProvider, LLMProviderError

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Thin wrapper around ``google.genai.Client.models.generate_content``.

    The SDK is imported lazily so the app runs without it when AI is off.
    ``client`` can be injected for tests; real requests are never made in CI.
    """

    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise LLMProviderError("Gemini API key is missing.")
        self.model = model
        self.timeout_seconds = timeout_seconds

        if client is not None:
            self._client = client
            self._types = None
            return

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMProviderError("google-genai package is not installed.") from exc

        self._types = types
        self._client = genai.Client(
            api_key=api_key,
            # HttpOptions.timeout is in milliseconds.
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    @property
    def is_available(self) -> bool:
        return True

    def _build_config(self, system_instruction: str | None, json_output: bool) -> Any:
        options: dict[str, Any] = {"temperature": 0.0}
        if system_instruction:
            options["system_instruction"] = system_instruction
        if json_output:
            options["response_mime_type"] = "application/json"
        if self._types is None:
            return options
        return self._types.GenerateContentConfig(**options)

    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        json_output: bool = False,
    ) -> str:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._build_config(system_instruction, json_output),
            )
        except Exception as exc:  # SDK, network and timeout errors
            # Log only the error type: messages may echo request details.
            logger.warning("Gemini request failed: %s", type(exc).__name__)
            raise LLMProviderError(
                f"Gemini request failed ({type(exc).__name__})."
            ) from exc

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise LLMProviderError("Gemini returned an empty response.")
        return text
