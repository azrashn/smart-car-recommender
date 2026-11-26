"""Tests for T12: POST /api/preferences/form and the form normaliser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.preferences.form_parser import normalize_preference
from app.schemas.preference import BodyType, FuelType, Preference

FORM_URL = "/api/preferences/form"
FIXTURES_FILE = Path(__file__).parent / "fixtures" / "sample_preferences.json"

CONTRACT_EXAMPLE = {
    "budget_max_try": 2000000,
    "budget_min_try": 1500000,
    "usage_type": "family",
    "annual_km": 25000,
    "transmission": "automatic",
    "fuel_types": ["petrol", "hybrid"],
    "body_types": ["suv"],
    "min_seats": 5,
    "priorities": {
        "fuel_economy": "medium",
        "interior_space": "high",
        "performance": "low",
        "budget_fit": "medium",
        "safety": "high",
    },
    "language": "tr",
}


def _fixture_samples() -> dict[str, dict]:
    with open(FIXTURES_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {
        key: {k: v for k, v in value.items() if not k.startswith("_")}
        for key, value in raw.items()
        if not key.startswith("_")
    }


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


def test_contract_example_returns_200_and_same_body(client: TestClient) -> None:
    response = client.post(FORM_URL, json=CONTRACT_EXAMPLE)

    assert response.status_code == 200
    assert response.json() == CONTRACT_EXAMPLE


def test_minimal_request_fills_defaults(client: TestClient) -> None:
    response = client.post(FORM_URL, json={"budget_max_try": 1000000})

    assert response.status_code == 200
    body = response.json()
    assert body["budget_max_try"] == 1000000
    assert body["language"] == "tr"
    assert body["fuel_types"] == []
    assert body["body_types"] == []
    assert set(body["priorities"].values()) == {"medium"}


def test_duplicate_list_values_are_removed(client: TestClient) -> None:
    payload = {
        "budget_max_try": 1000000,
        "fuel_types": ["petrol", "hybrid", "petrol"],
        "body_types": ["suv", "suv", "sedan"],
    }

    body = client.post(FORM_URL, json=payload).json()

    assert body["fuel_types"] == ["petrol", "hybrid"]
    assert body["body_types"] == ["suv", "sedan"]


def test_missing_budget_returns_422(client: TestClient) -> None:
    response = client.post(FORM_URL, json={"language": "en"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "budget_max_try"]


def test_budget_min_greater_than_max_returns_422(client: TestClient) -> None:
    payload = {"budget_max_try": 1500000, "budget_min_try": 1800000}

    response = client.post(FORM_URL, json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body"]


def test_unknown_field_returns_422(client: TestClient) -> None:
    response = client.post(FORM_URL, json={"budget_max_try": 1000000, "color": "red"})

    assert response.status_code == 422


def test_invalid_enum_returns_422(client: TestClient) -> None:
    response = client.post(FORM_URL, json={"budget_max_try": 1000000, "fuel_types": ["lpg"]})

    assert response.status_code == 422


@pytest.mark.parametrize("key", sorted(_fixture_samples()))
def test_all_fixture_samples_return_200(client: TestClient, key: str) -> None:
    response = client.post(FORM_URL, json=_fixture_samples()[key])

    assert response.status_code == 200


def test_static_frontend_still_served(client: TestClient) -> None:
    response = client.get("/survey.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_normalize_preference_dedupes_and_keeps_order() -> None:
    pref = Preference.model_construct(
        budget_max_try=1000000,
        fuel_types=[FuelType.hybrid, FuelType.petrol, FuelType.hybrid],
        body_types=[BodyType.suv, BodyType.suv],
    )

    result = normalize_preference(pref)

    assert result.fuel_types == [FuelType.hybrid, FuelType.petrol]
    assert result.body_types == [BodyType.suv]


def test_normalize_preference_does_not_mutate_input_or_other_fields() -> None:
    pref = Preference.model_validate(CONTRACT_EXAMPLE)

    result = normalize_preference(pref)

    assert result is not pref
    assert result == pref
