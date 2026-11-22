"""Tests for T01: application skeleton, settings and the /health endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.config import BASE_DIR, Settings, get_settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


def test_health_returns_200_and_status_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["ai_provider"] in {"none", "gemini"}


def test_health_is_listed_in_openapi_docs(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


def test_static_frontend_is_served(client: TestClient) -> None:
    response = client.get("/survey.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_settings_defaults_without_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_NAME", "AI_PROVIDER", "GEMINI_API_KEY", "DATABASE_URL", "VEHICLES_CSV_PATH"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "AutoMatch"
    assert settings.ai_provider == "none"
    assert settings.gemini_api_key is None
    assert settings.database_url.startswith("sqlite:///")
    assert settings.vehicles_csv_path == BASE_DIR / "data" / "vehicles.csv"


def test_settings_read_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "gemini"
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "test-key"


def test_blank_api_key_is_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    assert Settings(_env_file=None).gemini_api_key is None


def test_unknown_ai_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "unknown")

    with pytest.raises(ValueError):
        Settings(_env_file=None)
