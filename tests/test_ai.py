"""Tests for the M4 AI layer (T30). No real Gemini requests are made."""

from __future__ import annotations

import pytest

from app.ai import (
    AISettings,
    LLMProviderError,
    LLMUnavailableError,
    NoneProvider,
    create_provider,
    get_provider,
    load_ai_settings,
    reset_provider,
)
from app.ai.gemini import GeminiProvider

AI_ENV_VARS = ("AI_PROVIDER", "GEMINI_API_KEY", "GEMINI_MODEL", "AI_TIMEOUT_SECONDS")


@pytest.fixture(autouse=True)
def clean_ai_env(monkeypatch):
    for name in AI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    reset_provider()
    yield
    reset_provider()


# --- Fakes for the google-genai client ---------------------------------------


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, text="ok", error=None):
        self.text = text
        self.error = error
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error is not None:
            raise self.error
        return FakeResponse(self.text)


class FakeClient:
    def __init__(self, **kwargs):
        self.models = FakeModels(**kwargs)


def make_gemini(client):
    return GeminiProvider(
        api_key="test-key", model="test-model", timeout_seconds=5, client=client
    )


# --- Configuration -----------------------------------------------------------


def test_settings_default_to_none_provider():
    settings = load_ai_settings(use_dotenv=False)
    assert settings.provider == "none"
    assert settings.gemini_api_key is None
    assert settings.timeout_seconds > 0


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", " Gemini ")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    monkeypatch.setenv("GEMINI_MODEL", "custom-model")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "3.5")
    settings = load_ai_settings(use_dotenv=False)
    assert settings.provider == "gemini"
    assert settings.gemini_api_key == "secret-value"
    assert settings.gemini_model == "custom-model"
    assert settings.timeout_seconds == 3.5


@pytest.mark.parametrize("value", ["openai", "", "  "])
def test_unknown_provider_falls_back_to_none(monkeypatch, value):
    monkeypatch.setenv("AI_PROVIDER", value)
    assert load_ai_settings(use_dotenv=False).provider == "none"


@pytest.mark.parametrize("value", ["abc", "0", "-2"])
def test_invalid_timeout_uses_default(monkeypatch, value):
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", value)
    assert load_ai_settings(use_dotenv=False).timeout_seconds == 10.0


def test_settings_repr_hides_api_key():
    settings = AISettings(provider="gemini", gemini_api_key="super-secret")
    assert "super-secret" not in repr(settings)
    assert "<set>" in repr(settings)


# --- NoneProvider ------------------------------------------------------------


def test_none_provider_is_unavailable_and_raises():
    provider = NoneProvider()
    assert provider.name == "none"
    assert provider.is_available is False
    with pytest.raises(LLMUnavailableError):
        provider.generate("hello")


# --- Factory -----------------------------------------------------------------


def test_factory_returns_none_provider_by_default():
    assert isinstance(create_provider(AISettings()), NoneProvider)


def test_factory_gemini_without_key_degrades_to_none(caplog):
    provider = create_provider(AISettings(provider="gemini", gemini_api_key=None))
    assert isinstance(provider, NoneProvider)
    assert "GEMINI_API_KEY" in caplog.text


def test_factory_gemini_init_error_degrades_to_none(monkeypatch):
    def broken_init(self, **kwargs):
        raise LLMProviderError("google-genai package is not installed.")

    monkeypatch.setattr(GeminiProvider, "__init__", broken_init)
    provider = create_provider(AISettings(provider="gemini", gemini_api_key="k"))
    assert isinstance(provider, NoneProvider)


def test_factory_builds_gemini_provider_with_key():
    pytest.importorskip("google.genai")
    provider = create_provider(
        AISettings(
            provider="gemini", gemini_api_key="k", gemini_model="m", timeout_seconds=2
        )
    )
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "m"
    assert provider.is_available is True


def test_get_provider_is_cached_and_resettable(monkeypatch):
    first = get_provider()
    assert isinstance(first, NoneProvider)
    assert get_provider() is first
    reset_provider()
    assert get_provider() is not first


# --- GeminiProvider (mocked client) ------------------------------------------


def test_gemini_returns_text_and_passes_options():
    client = FakeClient(text='{"budget_max": 1000000}')
    provider = make_gemini(client)

    result = provider.generate("prompt", system_instruction="sys", json_output=True)

    assert result == '{"budget_max": 1000000}'
    call = client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["contents"] == "prompt"
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["system_instruction"] == "sys"
    assert call["config"]["temperature"] == 0.0


def test_gemini_plain_text_has_no_json_mime_type():
    client = FakeClient(text="hello")
    make_gemini(client).generate("prompt")
    assert "response_mime_type" not in client.models.calls[0]["config"]


def test_gemini_wraps_sdk_errors_without_leaking_details():
    client = FakeClient(error=TimeoutError("request with key=test-key timed out"))
    with pytest.raises(LLMProviderError) as exc_info:
        make_gemini(client).generate("prompt")
    assert "test-key" not in str(exc_info.value)
    assert "TimeoutError" in str(exc_info.value)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_gemini_empty_response_is_an_error(text):
    with pytest.raises(LLMProviderError):
        make_gemini(FakeClient(text=text)).generate("prompt")


def test_gemini_requires_key_without_injected_client():
    with pytest.raises(LLMProviderError):
        GeminiProvider(api_key="", model="m", timeout_seconds=1)
