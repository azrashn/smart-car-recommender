"""Tests for the Scenario Lab service and POST /api/scenarios (T50).

The service tests run on a fixed fixture catalogue (``tests/fixtures/sample_vehicles.csv``),
so they do not change when ``data/vehicles.csv`` grows. API tests patch the catalogue
loader for the same reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine import service as engine_service
from app.main import app
from app.scenarios.schemas import PriorityOverrides, ScenarioRequest
from app.scenarios.service import (
    DEFAULT_ANNUAL_KM,
    DEFAULT_DIESEL_PER_L,
    DEFAULT_PETROL_PER_L,
    build_prices,
    merge_priorities,
    run_scenario,
)
from app.schemas.preference import Preference, Priority, ScoringPriorities

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_vehicles.csv"
BASE = {"budget_max_try": 3_500_000}


@pytest.fixture(scope="module")
def catalogue():
    return engine_service.load_catalog_vehicles(FIXTURE_CSV)


@pytest.fixture()
def client(monkeypatch, catalogue):
    """TestClient whose catalogue is the fixture, not the live data file."""
    monkeypatch.setattr(engine_service, "load_catalog_vehicles", lambda *a, **k: list(catalogue))
    import app.scenarios.service as scenarios_service

    monkeypatch.setattr(scenarios_service, "load_catalog_vehicles", lambda *a, **k: list(catalogue))
    return TestClient(app)


def _run(catalogue, preference=None, overrides=None, vehicles=None):
    payload = {"preference": dict(preference or BASE)}
    if overrides is not None:
        payload["overrides"] = overrides
    return run_scenario(ScenarioRequest.model_validate(payload), vehicles if vehicles is not None else catalogue)


def _by_id(result):
    return {item.vehicle_id: item for item in result.recommendations}


def _with_fuel(catalogue, fuel_type, consumption_l=None):
    """Copy of the catalogue where the first petrol car becomes ``fuel_type``."""
    vehicles = list(catalogue)
    for i, v in enumerate(vehicles):
        if v.fuel_type == "petrol":
            vehicles[i] = v.model_copy(update={"fuel_type": fuel_type, "consumption_l_100km": consumption_l or v.consumption_l_100km})
            return vehicles, v.id
    raise AssertionError("no petrol car in fixture")


# --- helpers ---------------------------------------------------------------------
def test_merge_priorities_keeps_unset_keys_from_base():
    base = ScoringPriorities(fuel_economy=Priority.high, budget_fit=Priority.high)
    merged = merge_priorities(base, PriorityOverrides(budget_fit=Priority.low))
    assert merged.fuel_economy is Priority.high
    assert merged.budget_fit is Priority.low
    assert merged.safety is Priority.medium


def test_merge_priorities_without_override_returns_base():
    base = ScoringPriorities()
    assert merge_priorities(base, None) is base


def test_build_prices_defaults_and_diesel_ratio():
    default = build_prices(None)
    assert default.petrol_per_l == DEFAULT_PETROL_PER_L
    assert default.diesel_per_l == pytest.approx(DEFAULT_DIESEL_PER_L)
    doubled = build_prices(2 * DEFAULT_PETROL_PER_L)
    assert doubled.diesel_per_l == pytest.approx(2 * DEFAULT_DIESEL_PER_L)
    assert doubled.electricity_per_kwh == default.electricity_per_kwh
    assert build_prices(None, 12.0).electricity_per_kwh == 12.0


# --- service ---------------------------------------------------------------------
def test_empty_overrides_reproduce_the_base_ranking(catalogue):
    result = _run(catalogue)
    assert result.status == "success"
    assert result.recommendations
    for item in result.recommendations:
        assert item.base_rank == item.rank
        assert item.rank_change == 0


def test_priority_override_changes_weights_used(catalogue):
    result = _run(catalogue, overrides={"priorities": {"performance": "high"}})
    assert result.weights_used["performance"] == 3
    assert result.weights_used["safety"] == 2


def test_rank_change_is_base_rank_minus_rank(catalogue):
    result = _run(catalogue, overrides={"priorities": {"performance": "high", "fuel_economy": "low"}})
    for item in result.recommendations:
        if item.base_rank is None:
            assert item.rank_change is None
        else:
            assert item.rank_change == item.base_rank - item.rank


def test_vehicle_outside_the_base_top_five_has_no_base_rank(catalogue):
    base = _run(catalogue)
    base_ids = {i.vehicle_id for i in base.recommendations}
    seen_new = False
    for prios in ({"performance": "high", "fuel_economy": "low", "budget_fit": "low"}, {"safety": "high", "budget_fit": "low"}):
        for item in _run(catalogue, overrides={"priorities": prios}).recommendations:
            if item.vehicle_id not in base_ids:
                assert item.base_rank is None and item.rank_change is None
                seen_new = True
    assert seen_new, "fixture should let at least one vehicle enter the top 5"


def test_annual_km_override_scales_cost_linearly(catalogue):
    low = _by_id(_run(catalogue, overrides={"annual_km": 10_000}))
    high = _by_id(_run(catalogue, overrides={"annual_km": 20_000}))
    assert low.keys() == high.keys()
    for vid, item in low.items():
        assert item.estimated_annual_cost_try is not None
        assert high[vid].estimated_annual_cost_try == pytest.approx(2 * item.estimated_annual_cost_try, rel=1e-3)


def test_annual_km_falls_back_to_preference_then_default(catalogue):
    assert _run(catalogue).annual_km_used == DEFAULT_ANNUAL_KM
    assert _run(catalogue, preference={**BASE, "annual_km": 25_000}).annual_km_used == 25_000
    assert _run(catalogue, preference={**BASE, "annual_km": 25_000}, overrides={"annual_km": 8_000}).annual_km_used == 8_000


def test_fuel_price_changes_petrol_cost_only(catalogue):
    base = _by_id(_run(catalogue, overrides={"annual_km": 20_000}))
    pricey = _by_id(_run(catalogue, overrides={"annual_km": 20_000, "fuel_price_try": 2 * DEFAULT_PETROL_PER_L}))
    kinds = set()
    for vid, item in base.items():
        if item.fuel_type == "electric":
            assert pricey[vid].estimated_annual_cost_try == item.estimated_annual_cost_try
        else:
            assert pricey[vid].estimated_annual_cost_try == pytest.approx(2 * item.estimated_annual_cost_try, rel=1e-3)
        kinds.add(item.fuel_type)
    assert "petrol" in kinds


def test_diesel_cost_scales_with_the_derived_diesel_price(catalogue):
    vehicles, vid = _with_fuel(catalogue, "diesel")
    pref = {"budget_max_try": 9_000_000}
    base = _by_id(_run(catalogue, preference=pref, overrides={"annual_km": 20_000}, vehicles=vehicles))
    doubled = _run(catalogue, preference=pref, overrides={"annual_km": 20_000, "fuel_price_try": 2 * DEFAULT_PETROL_PER_L}, vehicles=vehicles)
    assert doubled.diesel_price_try_used == pytest.approx(2 * DEFAULT_DIESEL_PER_L, abs=0.01)
    if vid in base:
        assert _by_id(doubled)[vid].estimated_annual_cost_try == pytest.approx(2 * base[vid].estimated_annual_cost_try, rel=1e-3)


def test_electricity_price_changes_only_electric_cost(catalogue):
    base = _by_id(_run(catalogue, overrides={"annual_km": 20_000}))
    pricey = _by_id(_run(catalogue, overrides={"annual_km": 20_000, "electricity_price_try": 17.0}))
    electric = [vid for vid, i in base.items() if i.fuel_type == "electric"]
    assert electric, "fixture has electric cars in the top 5"
    for vid, item in base.items():
        if vid in electric:
            assert pricey[vid].estimated_annual_cost_try == pytest.approx(2 * item.estimated_annual_cost_try, rel=1e-3)
        else:
            assert pricey[vid].estimated_annual_cost_try == item.estimated_annual_cost_try


def test_missing_consumption_gives_no_cost_instead_of_a_guess(catalogue):
    vehicles = [v.model_copy(update={"consumption_l_100km": None}) if v.fuel_type == "petrol" else v for v in catalogue]
    result = _run(catalogue, vehicles=vehicles)
    petrol = [i for i in result.recommendations if i.fuel_type == "petrol"]
    assert petrol
    assert all(i.estimated_annual_cost_try is None for i in petrol)


def test_no_matching_vehicle_returns_conflict_report(catalogue):
    result = _run(catalogue, preference={"budget_max_try": 100_000})
    assert result.status == "conflict"
    assert result.has_conflict is True


def test_run_scenario_does_not_mutate_the_base_preference(catalogue):
    pref = Preference.model_validate(BASE)
    before = pref.model_dump()
    run_scenario(ScenarioRequest(preference=pref, overrides={"priorities": {"safety": "high"}}), catalogue)
    assert pref.model_dump() == before


# --- HTTP ------------------------------------------------------------------------
def test_api_success_shape(client):
    response = client.post("/api/scenarios", json={"preference": BASE, "overrides": {"annual_km": 30_000}})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["annual_km_used"] == 30_000
    assert {"fuel_price_try_used", "diesel_price_try_used", "electricity_price_try_used"} <= set(body)
    first = body["recommendations"][0]
    assert {"rank", "base_rank", "rank_change", "estimated_annual_cost_try", "score_breakdown"} <= set(first)


def test_api_works_without_overrides(client):
    assert client.post("/api/scenarios", json={"preference": BASE}).status_code == 200


def test_api_returns_conflict_report_for_impossible_filters(client):
    response = client.post("/api/scenarios", json={"preference": {"budget_max_try": 100_000}})
    assert response.status_code == 200
    assert response.json()["status"] == "conflict"


@pytest.mark.parametrize(
    "overrides,ok",
    [
        ({"annual_km": 999}, False),
        ({"annual_km": 1_000}, True),
        ({"annual_km": 200_000}, True),
        ({"annual_km": 200_001}, False),
        ({"fuel_price_try": 0}, False),
        ({"fuel_price_try": -3}, False),
        ({"fuel_price_try": 1_000}, True),
        ({"fuel_price_try": 1_001}, False),
        ({"electricity_price_try": 0}, False),
        ({"electricity_price_try": 1_000}, True),
        ({"electricity_price_try": 1_001}, False),
        ({"priorities": {"safety": "extreme"}}, False),
        ({"unknown": 1}, False),
    ],
)
def test_api_override_bounds(client, overrides, ok):
    response = client.post("/api/scenarios", json={"preference": BASE, "overrides": overrides})
    assert response.status_code == (200 if ok else 422)


@pytest.mark.parametrize("payload", [{"preference": {"budget_max_try": -1}}, {"overrides": {}}])
def test_api_rejects_invalid_body(client, payload):
    assert client.post("/api/scenarios", json=payload).status_code == 422
