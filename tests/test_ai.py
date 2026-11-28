"""Tests for the M4 AI layer (T30, T33, T34). No real Gemini requests are made."""

from __future__ import annotations

import json
from pathlib import Path

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
from app.ai.conflict import (
    MAX_SUGGESTIONS_IN_TEXT,
    build_conflict_template,
    conflict_facts,
    explain_conflict,
    explain_conflict_report,
)
from app.ai.explanation import (
    MAX_EXPLANATION_CHARS,
    build_template_explanation,
    explain_recommendation,
    explain_recommendations,
    normalize_language,
    recommendation_facts,
)
from app.ai.gemini import GeminiProvider
from app.schemas.recommendation import ConflictReport, RecommendationResult

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


# --- T33: recommendation explanation -----------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


class FakeProvider:
    """Stand-in LLMProvider that records prompts and returns a fixed reply."""

    name = "fake"

    def __init__(self, reply="AI explanation.", error=None, available=True):
        self.reply = reply
        self.error = error
        self.available = available
        self.prompts = []

    @property
    def is_available(self):
        return self.available

    def generate(self, prompt, *, system_instruction=None, json_output=False):
        self.prompts.append(
            {"prompt": prompt, "system": system_instruction, "json": json_output}
        )
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def sample_result():
    data = json.loads((FIXTURES / "sample_results.json").read_text(encoding="utf-8"))
    return RecommendationResult.model_validate(data["recommendation_success"])


@pytest.fixture
def first_item(sample_result):
    return sample_result.recommendations[0]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("tr", "tr"), ("EN", "en"), ("en-US", "en"), ("de", "tr"), (None, "tr")],
)
def test_normalize_language(value, expected):
    assert normalize_language(value) == expected


def test_template_tr_uses_only_real_values(first_item):
    text = build_template_explanation(first_item, "tr")
    assert text.startswith("Toyota Corolla, 86/100 puanla 1. sırada.")
    # Top two sub-scores of the fixture: safety 100, fuel_economy 92.
    assert "güvenlik (100/100) ve yakıt ekonomisi (92/100)" in text
    assert first_item.strengths[0] in text
    assert first_item.weaknesses[0] in text


def test_template_en(first_item):
    text = build_template_explanation(first_item, "en")
    assert text.startswith("Toyota Corolla ranks #1 with a score of 86/100.")
    assert "safety (100/100) and fuel economy (92/100)" in text


def test_template_skips_missing_safety_and_empty_lists(first_item):
    item = first_item.model_copy(
        update={
            "score_breakdown": first_item.score_breakdown.model_copy(
                update={"safety": None}
            ),
            "strengths": [],
            "weaknesses": [],
        }
    )
    text = build_template_explanation(item, "tr")
    assert "güvenlik" not in text
    assert "Öne çıkan" not in text
    assert "Dikkat" not in text


def test_template_is_deterministic(first_item):
    assert build_template_explanation(first_item) == build_template_explanation(
        first_item
    )


def test_none_provider_uses_template(first_item):
    result = explain_recommendation(first_item, "tr", NoneProvider())
    assert result.method == "template"
    assert result.text == build_template_explanation(first_item, "tr")


def test_ai_explanation_used_when_available(first_item):
    provider = FakeProvider(reply="  Corolla is a\n balanced choice.  ")
    result = explain_recommendation(first_item, "en", provider)
    assert result.method == "ai"
    assert result.text == "Corolla is a balanced choice."
    sent = provider.prompts[0]
    assert "English" in sent["prompt"]
    assert "Do not invent" in sent["system"]
    assert sent["json"] is False


def test_prompt_contains_only_engine_facts(first_item):
    facts = recommendation_facts(first_item)
    assert "explanation" not in facts
    assert "estimated_annual_cost_try" not in facts
    assert facts["score"] == first_item.score
    provider = FakeProvider()
    explain_recommendation(first_item, "tr", provider)
    assert '"score": 86.4' in provider.prompts[0]["prompt"]


@pytest.mark.parametrize(
    "error", [LLMProviderError("timeout"), LLMUnavailableError("off")]
)
def test_ai_error_falls_back_to_template(first_item, error):
    result = explain_recommendation(first_item, "tr", FakeProvider(error=error))
    assert result.method == "template"


@pytest.mark.parametrize("reply", ["", "   ", "x" * (MAX_EXPLANATION_CHARS + 1)])
def test_invalid_ai_reply_falls_back_to_template(first_item, reply):
    result = explain_recommendation(first_item, "tr", FakeProvider(reply=reply))
    assert result.method == "template"


def test_explain_recommendations_only_changes_explanation(sample_result):
    explained = explain_recommendations(sample_result, "en", NoneProvider())
    for before, after in zip(
        sample_result.recommendations, explained.recommendations, strict=True
    ):
        assert after.explanation == build_template_explanation(before, "en")
        assert after.model_dump(exclude={"explanation"}) == before.model_dump(
            exclude={"explanation"}
        )
    assert explained.total_matches == sample_result.total_matches
    # Input is not mutated.
    assert sample_result.recommendations[0].explanation.startswith("Toyota Corolla")


def test_explanation_uses_default_provider_when_ai_off(first_item):
    assert explain_recommendation(first_item).method == "template"


# --- T34: conflict explanation -----------------------------------------------


@pytest.fixture
def conflict_report():
    data = json.loads((FIXTURES / "sample_results.json").read_text(encoding="utf-8"))
    return ConflictReport.model_validate(data["conflict_example"])


def test_conflict_template_tr_uses_report_values(conflict_report):
    text = build_conflict_template(conflict_report, "tr")
    assert text.startswith("Seçtiğiniz kriterlerin tamamına uyan araç bulunamadı.")
    assert "bütçe üst sınırı, kasa tipi ve yakıt türü" in text
    assert (
        "Bütçe üst sınırı 1.500.000 TL yerine 1.790.000 TL olursa "
        "1 araç daha uygun hale gelir." in text
    )
    assert "Yakıt türü elektrikli yerine benzinli olursa" in text


def test_conflict_template_en(conflict_report):
    text = build_conflict_template(conflict_report, "en")
    assert text.startswith("No vehicle matches all of your criteria.")
    assert "maximum budget, body type and fuel type" in text
    assert (
        "Changing maximum budget from 1,500,000 TL to 1,790,000 TL "
        "would unlock 1 more vehicle." in text
    )
    assert "from electric to petrol" in text


def test_conflict_counts_come_only_from_report(conflict_report):
    suggestion = conflict_report.suggestions[0].model_copy(
        update={"additional_matches_unlocked": 7}
    )
    report = conflict_report.model_copy(update={"suggestions": [suggestion]})
    assert "7 more vehicles" in build_conflict_template(report, "en")
    assert "7 araç daha" in build_conflict_template(report, "tr")


def test_conflict_template_without_suggestions(conflict_report):
    report = conflict_report.model_copy(update={"suggestions": []})
    tr = build_conflict_template(report, "tr")
    assert "esnetmeyi deneyebilirsiniz" in tr
    assert "olursa" not in tr
    assert "Try relaxing one of your criteria." in build_conflict_template(report, "en")


def test_conflict_template_limits_suggestions(conflict_report):
    many = [conflict_report.suggestions[0]] * (MAX_SUGGESTIONS_IN_TEXT + 2)
    report = conflict_report.model_copy(update={"suggestions": many})
    assert build_conflict_template(report, "tr").count("olursa") == (
        MAX_SUGGESTIONS_IN_TEXT
    )
    assert len(conflict_facts(report)["suggestions"]) == MAX_SUGGESTIONS_IN_TEXT


def test_conflict_template_handles_unknown_constraint_and_lists(conflict_report):
    suggestion = conflict_report.suggestions[0].model_copy(
        update={
            "constraint": "colour",
            "current_value": ["suv", "sedan"],
            "suggested_value": "any",
        }
    )
    report = conflict_report.model_copy(
        update={"conflicting_constraints": ["colour"], "suggestions": [suggestion]}
    )
    text = build_conflict_template(report, "en")
    assert "The blocking criteria are: colour." in text
    assert "from SUV, sedan to any" in text


def test_conflict_facts_exclude_free_text(conflict_report):
    facts = conflict_facts(conflict_report)
    assert facts["conflicting_constraints"] == ["budget_max", "body_type", "fuel_type"]
    assert all("message" not in s for s in facts["suggestions"])
    assert "explanation" not in facts


def test_conflict_none_provider_uses_template(conflict_report):
    result = explain_conflict(conflict_report, "en", NoneProvider())
    assert result.method == "template"
    assert result.text == build_conflict_template(conflict_report, "en")


def test_conflict_ai_used_when_available(conflict_report):
    provider = FakeProvider(reply="Budget and fuel type conflict.")
    result = explain_conflict(conflict_report, "en", provider)
    assert result.method == "ai"
    assert result.text == "Budget and fuel type conflict."
    assert '"additional_matches_unlocked": 1' in provider.prompts[0]["prompt"]
    assert "Do not invent" in provider.prompts[0]["system"]


def test_conflict_ai_error_falls_back(conflict_report):
    provider = FakeProvider(error=LLMProviderError("timeout"))
    assert explain_conflict(conflict_report, "tr", provider).method == "template"


def test_explain_conflict_report_only_changes_explanation(conflict_report):
    explained = explain_conflict_report(conflict_report, "tr", NoneProvider())
    assert explained.explanation == build_conflict_template(conflict_report, "tr")
    assert explained.model_dump(exclude={"explanation"}) == (
        conflict_report.model_dump(exclude={"explanation"})
    )
    assert conflict_report.explanation.startswith("Piyasa koşullarında")
