"""POST /api/recommendations uses M4 explanations (T33 integration with M3's T25)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.ai.explanation as explanation
from app.ai import reset_provider
from app.ai.explanation import build_template_explanation
from app.engine.service import generate_recommendations
from app.main import create_app
from app.schemas.preference import Preference

URL = "/api/recommendations"
PAYLOAD = {"budget_max_try": 2_500_000, "transmission": "automatic", "language": "tr"}


@pytest.fixture(autouse=True)
def ai_off(monkeypatch):
    for name in ("AI_PROVIDER", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    reset_provider()
    yield
    reset_provider()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def engine_result(payload):
    return generate_recommendations(Preference.model_validate(payload))


def test_explanations_come_from_m4_template_when_ai_is_off(client):
    body = client.post(URL, json=PAYLOAD).json()
    engine = engine_result(PAYLOAD)
    assert body["status"] == "success"
    for got, item in zip(body["recommendations"], engine.recommendations, strict=True):
        assert got["explanation"] == build_template_explanation(item, "tr")


def test_only_explanation_changes(client):
    body = client.post(URL, json=PAYLOAD).json()
    engine = engine_result(PAYLOAD).model_dump(mode="json")
    for got, expected in zip(body["recommendations"], engine["recommendations"], strict=True):
        got.pop("explanation")
        expected.pop("explanation")
        assert got == expected
    for key in ("total_matches", "applied_filters", "weights_used"):
        assert body[key] == engine[key]


def test_language_follows_preference(client):
    body = client.post(URL, json={**PAYLOAD, "language": "en"}).json()
    assert " ranks #1 with a score of " in body["recommendations"][0]["explanation"]


def test_ai_explanation_is_used_when_available(client, monkeypatch):
    class FakeProvider:
        name = "fake"
        is_available = True

        def generate(self, prompt, *, system_instruction=None, json_output=False):
            return "Dengeli ve güvenli bir seçim."

    monkeypatch.setattr(explanation, "get_provider", lambda: FakeProvider())
    body = client.post(URL, json=PAYLOAD).json()
    assert {r["explanation"] for r in body["recommendations"]} == {"Dengeli ve güvenli bir seçim."}


def test_conflict_report_is_returned_unchanged(client):
    payload = {"budget_max_try": 900_000, "fuel_types": ["electric"], "body_types": ["suv"]}
    body = client.post(URL, json=payload).json()
    assert body["status"] == "conflict"
    assert body == engine_result(payload).model_dump(mode="json")
