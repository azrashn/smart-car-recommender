"""Tests for the Scenario Lab service and POST /api/scenarios (T50)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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

client = TestClient(app)

BASE = {"budget_max_try": 3_500_000}


def _run(preference=None, overrides=None):
    payload = {"preference": dict(preference or BASE)}
    if overrides is not None:
        payload["overrides"] = overrides
    return run_scenario(ScenarioRequest.model_validate(payload))


def _by_id(result):
    return {item.vehicle_id: item for item in result.recommendations}


def test_merge_priorities_keeps_unset_keys_from_base():
    base = ScoringPriorities(fuel_economy=Priority.high, budget_fit=Priority.high)
    merged = merge_priorities(base, PriorityOverrides(budget_fit=Priority.low))
    assert merged.fuel_economy is Priority.high  # untouched
    assert merged.budget_fit is Priority.low  # overridden
    assert merged.safety is Priority.medium  # default untouched


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


def test_empty_overrides_reproduce_the_base_ranking():
    result = _run()
    assert result.status == "success"
    for item in result.recommendations:
        assert item.base_rank == item.rank
        assert item.rank_change == 0


def test_priority_override_changes_weights_used():
    result = _run(overrides={"priorities": {"performance": "high"}})
    assert result.weights_used["performance"] == 3
    assert result.weights_used["safety"] == 2  # unset keys keep the base value


def test_annual_km_override_scales_cost_linearly():
    low = _by_id(_run(overrides={"annual_km": 10_000}))
    high = _by_id(_run(overrides={"annual_km": 20_000}))
    common = [i for i in low if i in high and low[i].estimated_annual_cost_try]
    assert common
    for vid in common:
        assert high[vid].estimated_annual_cost_try == pytest.approx(
            2 * low[vid].estimated_annual_cost_try, rel=1e-3
        )


def test_annual_km_falls_back_to_preference_then_default():
    assert _run().annual_km_used == DEFAULT_ANNUAL_KM
    assert _run(preference={**BASE, "annual_km": 25_000}).annual_km_used == 25_000
    assert _run(preference={**BASE, "annual_km": 25_000}, overrides={"annual_km": 8_000}).annual_km_used == 8_000


def test_fuel_price_override_changes_petrol_cost_but_not_electric():
    base = _by_id(_run(overrides={"annual_km": 20_000}))
    pricey = _by_id(_run(overrides={"annual_km": 20_000, "fuel_price_try": 2 * DEFAULT_PETROL_PER_L}))
    for vid, item in base.items():
        if vid not in pricey or item.estimated_annual_cost_try is None:
            continue
        if item.fuel_type == "electric":
            assert pricey[vid].estimated_annual_cost_try == item.estimated_annual_cost_try
        elif item.fuel_type in ("petrol", "hybrid"):
            assert pricey[vid].estimated_annual_cost_try == pytest.approx(
                2 * item.estimated_annual_cost_try, rel=1e-3
            )


def test_rank_change_is_base_rank_minus_rank():
    result = _run(overrides={"priorities": {"performance": "high", "fuel_economy": "low"}})
    for item in result.recommendations:
        if item.base_rank is None:
            assert item.rank_change is None
        else:
            assert item.rank_change == item.base_rank - item.rank


def test_no_matching_vehicle_returns_conflict_report():
    result = _run(preference={"budget_max_try": 100_000})
    assert result.status == "conflict"
    assert result.has_conflict is True


def test_api_success_shape():
    response = client.post("/api/scenarios", json={"preference": BASE, "overrides": {"annual_km": 30_000}})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["annual_km_used"] == 30_000
    first = body["recommendations"][0]
    assert {"rank", "base_rank", "rank_change", "estimated_annual_cost_try", "score_breakdown"} <= set(first)


def test_api_works_without_overrides():
    assert client.post("/api/scenarios", json={"preference": BASE}).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"preference": BASE, "overrides": {"annual_km": 5}},
        {"preference": BASE, "overrides": {"annual_km": 500_000}},
        {"preference": BASE, "overrides": {"fuel_price_try": 0}},
        {"preference": BASE, "overrides": {"fuel_price_try": -3}},
        {"preference": BASE, "overrides": {"priorities": {"safety": "extreme"}}},
        {"preference": BASE, "overrides": {"unknown": 1}},
        {"preference": {"budget_max_try": -1}},
        {"overrides": {}},
    ],
)
def test_api_rejects_invalid_input(payload):
    assert client.post("/api/scenarios", json=payload).status_code == 422


def test_run_scenario_does_not_mutate_the_base_preference():
    pref = Preference.model_validate(BASE)
    before = pref.model_dump()
    run_scenario(ScenarioRequest(preference=pref, overrides={"priorities": {"safety": "high"}}))
    assert pref.model_dump() == before
