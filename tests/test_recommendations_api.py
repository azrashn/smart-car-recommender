"""Tests for POST /api/recommendations endpoint and service (T25)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.engine.service import generate_recommendations, load_catalog_vehicles
from app.main import create_app
from app.schemas.preference import Preference
from app.schemas.recommendation import ConflictReport, RecommendationResult


@pytest.fixture
def client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


def test_load_catalog_vehicles_reads_production_data() -> None:
    """load_catalog_vehicles must load data/vehicles.csv, not tests/fixtures/."""
    vehicles = load_catalog_vehicles()
    assert len(vehicles) >= 10
    # Production data/vehicles.csv contains Togg T10X; sample_vehicles.csv does not
    assert any(v.brand == "Togg" for v in vehicles)


def test_post_recommendations_endpoint_returns_top_5(client: TestClient) -> None:
    """POST /api/recommendations is registered in app.main and returns up to 5 cars."""
    payload = {
        "budget_max_try": 3_000_000,
        "transmission": "automatic",
        "min_seats": 5,
        "priorities": {
            "fuel_economy": "high",
            "budget_fit": "medium",
            "safety": "high",
        },
    }
    response = client.post("/api/recommendations", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["total_matches"] > 0
    assert 1 <= len(body["recommendations"]) <= 5
    assert body["weights_used"]["fuel_economy"] == 3
    assert body["weights_used"]["budget_fit"] == 2
    assert body["weights_used"]["safety"] == 3

    for rec in body["recommendations"]:
        assert 0.0 <= rec["score"] <= 100.0
        assert len(rec["strengths"]) > 0
        assert rec["explanation"]


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {},  # missing required budget_max_try
        {"budget_max_try": -500_000},  # negative budget
        {"budget_max_try": 2_000_000, "unknown_field": "abc"},  # extra="forbid"
        {"budget_max_try": 1_500_000, "budget_min_try": 2_000_000},  # min > max
        {"budget_max_try": 2_000_000, "min_seats": 1},  # below min_seats=2
    ],
)
def test_post_recommendations_rejects_invalid_input_with_422(
    client: TestClient,
    invalid_payload: dict,
) -> None:
    """Router validates body with Preference schema and returns 422 on bad input."""
    response = client.post("/api/recommendations", json=invalid_payload)
    assert response.status_code == 422


def test_post_recommendations_conflict_report(client: TestClient) -> None:
    """Unsatisfiable constraints return ConflictReport with actionable suggestions."""
    payload = {
        "budget_max_try": 1_000_000,
        "fuel_types": ["electric"],
        "body_types": ["suv"],
    }
    response = client.post("/api/recommendations", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "conflict"
    assert body["has_conflict"] is True
    assert "budget_max" in body["conflicting_constraints"]
    assert len(body["suggestions"]) > 0
    assert body["suggestions"][0]["additional_matches_unlocked"] >= 1


def test_min_seats_hard_filter_is_applied(client: TestClient) -> None:
    """Preference.min_seats must be mapped via hard_filter_criteria() and filter vehicles."""
    # All vehicles in data/vehicles.csv currently have 5 seats -> min_seats=7 yields conflict
    payload = {
        "budget_max_try": 5_000_000,
        "min_seats": 7,
    }
    response = client.post("/api/recommendations", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "conflict"
    assert "seats_min" in body["conflicting_constraints"]
    assert any(s["constraint"] == "seats_min" for s in body["suggestions"])


def test_missing_data_is_none_not_zero_in_score_breakdown() -> None:
    """NFR-04: Missing vehicle fields (e.g. trunk_l=None) must be None in ScoreBreakdown, not 0.0."""
    vehicles = load_catalog_vehicles()
    # Opel Corsa in data/vehicles.csv has trunk_l=None and euro_ncap_stars=None
    pref = Preference(budget_max_try=1_600_000, transmission="manual", body_types=["hatchback"])
    result = generate_recommendations(pref, vehicles=vehicles)

    assert isinstance(result, RecommendationResult)
    corsa = next((r for r in result.recommendations if r.model == "Corsa"), None)
    assert corsa is not None
    assert corsa.score_breakdown.interior_space is None
    assert corsa.score_breakdown.safety is None


def test_service_uses_full_catalogue_bounds_not_filtered_subset() -> None:
    """Filtering down to a single vehicle must keep its full-catalogue sub-scores."""
    vehicles = load_catalog_vehicles()
    # Very narrow filter that matches only 1 vehicle (Dacia Sandero at 1,390,000 TL)
    pref_single = Preference(budget_max_try=1_400_000)
    res_single = generate_recommendations(pref_single, vehicles=vehicles)

    assert isinstance(res_single, RecommendationResult)
    assert res_single.total_matches == 1
    sandero_single = res_single.recommendations[0]

    # Compare against unrestricted catalogue scoring
    pref_all = Preference(budget_max_try=10_000_000)
    res_all = generate_recommendations(pref_all, vehicles=vehicles)
    assert isinstance(res_all, RecommendationResult)
    # Sandero's performance (100 HP out of 90-530 HP) must NOT be 100.0
    assert sandero_single.score_breakdown.performance is not None
    assert sandero_single.score_breakdown.performance < 50.0


def test_service_accepts_preference_instance() -> None:
    """generate_recommendations works directly with a validated Preference object."""
    vehicles = load_catalog_vehicles()
    pref = Preference(budget_max_try=2_500_000)
    result = generate_recommendations(pref, vehicles=vehicles)

    assert isinstance(result, (RecommendationResult, ConflictReport))
    assert isinstance(result, RecommendationResult)
    assert len(result.recommendations) == 5
