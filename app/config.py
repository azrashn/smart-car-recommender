"""Application settings, read from environment variables and the ``.env`` file.

Usage::

    from app.config import get_settings

    settings = get_settings()
    settings.database_url

Environment variables take precedence over ``.env``; ``.env`` takes precedence
over the defaults below. See ``.env.example`` for every supported variable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = BASE_DIR / "data"

AIProvider = Literal["none", "gemini"]
AppEnv = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Typed application settings. Field names map to upper-case env variables."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        # Unknown keys in .env (e.g. settings added by another module) are ignored.
        extra="ignore",
    )

    app_name: str = "AutoMatch"
    app_env: AppEnv = "development"

    # SQLite file in the project root; independent of the working directory.
    database_url: str = f"sqlite:///{(BASE_DIR / 'automatch.db').as_posix()}"
    vehicles_csv_path: Path = DATA_DIR / "vehicles.csv"

    # AI is optional (NFR-02): "none" keeps every flow on rule/template fallbacks.
    ai_provider: AIProvider = "none"
    gemini_api_key: SecretStr | None = None

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _blank_key_to_none(cls, value: object) -> object:
        """Treat ``GEMINI_API_KEY=`` (empty, as in .env.example) as not set."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (use ``get_settings.cache_clear()`` in tests)."""
    return Settings()
