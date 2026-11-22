"""AI layer configuration (M4).

Settings are read from environment variables (optionally loaded from a local
``.env`` file). The AI layer is disabled by default: ``AI_PROVIDER=none``.

Note: once the shared ``app/config.py`` (T01) exists, these settings can be
moved there; the rest of the AI layer only depends on ``AISettings``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

SUPPORTED_PROVIDERS = ("none", "gemini")

DEFAULT_PROVIDER = "none"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 10.0


def _load_dotenv() -> None:
    """Load ``.env`` if python-dotenv is installed; never override real env vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)


def _parse_timeout(raw: str | None) -> float:
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class AISettings:
    """Immutable AI settings. ``gemini_api_key`` is excluded from ``repr``."""

    provider: str = DEFAULT_PROVIDER
    gemini_api_key: str | None = None
    gemini_model: str = DEFAULT_GEMINI_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __repr__(self) -> str:
        key_state = "set" if self.gemini_api_key else "missing"
        return (
            f"AISettings(provider={self.provider!r}, gemini_model={self.gemini_model!r}, "
            f"timeout_seconds={self.timeout_seconds}, gemini_api_key=<{key_state}>)"
        )


def load_ai_settings(*, use_dotenv: bool = True) -> AISettings:
    """Build ``AISettings`` from the environment.

    Unknown provider names fall back to ``none`` so a typo never breaks the app.
    """
    if use_dotenv:
        _load_dotenv()

    provider = (os.getenv("AI_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        provider = DEFAULT_PROVIDER

    api_key = (os.getenv("GEMINI_API_KEY") or "").strip() or None
    model = (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL

    return AISettings(
        provider=provider,
        gemini_api_key=api_key,
        gemini_model=model,
        timeout_seconds=_parse_timeout(os.getenv("AI_TIMEOUT_SECONDS")),
    )
