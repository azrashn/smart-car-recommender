"""Tests for GET /api/compare and the compare service (M5, T42, FR-10, FR-11)."""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.compare import service
from app.compare.service import parse_ids
from app.cost.defaults import DEFAULT_ANNUAL_KM, DEFAULT_ENERGY_PRICES
from app.engine.service import load_catalog_vehicles
from app.main import app
from app.schemas.vehicle import Vehicle

client = TestClient(app)

DIFFERENCE_FIELDS = {
    "price_try",
    "annual_cost_try",
    "power_hp",
    "trunk_l",
    "seats",
    "euro_ncap_stars",
}


def _round(value: float) -> int:
    return int(math.floor(value + 0.5))


def _catalog_ids(count: int) -> list[int]:
    ids = [vehicle.id for vehicle in load_catalog_vehicles()]
    if len(ids) < count:
        pytest.skip(f"catalogue has fewer than {count} vehicles")
    return ids[:count]


def _ids_param(ids: list[int]) -> str:
    return ",".join(str(vehicle_id) for vehicle_id in ids)


def _vehicle(vehicle_id: int, **overrides: Any) -> Vehicle:
    data: dict[str, Any] = {
        "id": vehicle_id,
        "brand": "Test",
        "model": f"Model {vehicle_id}",
        "variant": "1.0 Test",
        "year": 2026,
        "body_type": "hatchback",
        "fuel_type": "petrol",
        "transmission": "manual",
        "consumption_l_100km": 6.0,
        "consumption_kwh_100km": None,
        "range_km": None,
        "power_hp": 100,
        "seats": 5,
        "trunk_l": 350,
        "euro_ncap_stars": 4,
        "price_try": 1_500_000,
        "price_checked_at": dt.date(2026, 11, 19),
        "spec_source_url": "https://example.com/spec",
        "price_source_url": "https://example.com/price",
    }
    data.update(overrides)
    return Vehicle(**data)


@pytest.fixture
def fake_catalog(monkeypatch: pytest.MonkeyPatch):
    """Replace get_vehicles_by_ids with hand-made vehicles, kept in request order."""

    def install(*vehicles: Vehicle) -> None:
        by_id = {vehicle.id: vehicle for vehicle in vehicles}

        def fake_get_vehicles_by_ids(ids: list[int]) -> list[Vehicle]:
            return [by_id[vehicle_id] for vehicle_id in ids]

        monkeypatch.setattr(service, "get_vehicles_by_ids", fake_get_vehicles_by_ids)

    return install


def _get(ids: str, **params: Any) -> Any:
    return client.get("/api/compare", params={"ids": ids, **params})


def _differences(ids: str) -> dict[str, list[int]]:
    return _get(ids).json()["differences"]


def _by_id(body: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {vehicle["id"]: vehicle for vehicle in body["vehicles"]}


# --- Real catalogue -----------------------------------------------------------


def test_two_valid_ids_keep_request_order() -> None:
    first, second = _catalog_ids(2)
    response = client.get("/api/compare", params={"ids": f"{second},{first}"})
    assert response.status_code == 200
    vehicles = response.json()["vehicles"]
    assert len(vehicles) == 2
    assert [vehicle["id"] for vehicle in vehicles] == [second, first]


def test_three_valid_ids() -> None:
    ids = _catalog_ids(3)
    response = client.get("/api/compare", params={"ids": _ids_param(ids)})
    assert response.status_code == 200
    body = response.json()
    assert len(body["vehicles"]) == 3
    assert body["assumptions"]["annual_km"] == DEFAULT_ANNUAL_KM


def test_one_id_returns_422() -> None:
    (only,) = _catalog_ids(1)
    response = client.get("/api/compare", params={"ids": str(only)})
    assert response.status_code == 422


def test_four_ids_returns_422() -> None:
    response = client.get("/api/compare", params={"ids": "1,2,3,4"})
    assert response.status_code == 422


@pytest.mark.parametrize("raw", ["1,1", "1,abc", "1,,2", "0,1", "-1,2", ""])
def test_invalid_ids_return_422(raw: str) -> None:
    response = client.get("/api/compare", params={"ids": raw})
    assert response.status_code == 422


def test_missing_ids_parameter_returns_422() -> None:
    response = client.get("/api/compare")
    assert response.status_code == 422


def test_unknown_id_returns_404() -> None:
    (valid,) = _catalog_ids(1)
    response = client.get("/api/compare", params={"ids": f"{valid},999999"})
    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_zero_km_gives_zero_cost() -> None:
    ids = _catalog_ids(3)
    response = _get(_ids_param(ids), annual_km=0)
    assert response.status_code == 200
    costs = [vehicle["annual_cost_try"] for vehicle in response.json()["vehicles"]]
    assert all(cost == 0 for cost in costs if cost is not None)


@pytest.mark.parametrize("annual_km", [-1, 2_000_000])
def test_annual_km_out_of_range_returns_422(annual_km: int) -> None:
    ids = _catalog_ids(2)
    response = _get(_ids_param(ids), annual_km=annual_km)
    assert response.status_code == 422


def test_negative_price_returns_422() -> None:
    ids = _catalog_ids(2)
    response = _get(_ids_param(ids), petrol_price_try=-1)
    assert response.status_code == 422


def test_differences_never_contain_consumption() -> None:
    ids = _catalog_ids(3)
    response = client.get("/api/compare", params={"ids": _ids_param(ids)})
    differences = response.json()["differences"]
    assert "consumption_l_100km" not in differences
    assert "consumption_kwh_100km" not in differences
    assert set(differences) == DIFFERENCE_FIELDS


def test_same_request_is_deterministic() -> None:
    ids = _catalog_ids(3)
    params = {"ids": _ids_param(ids), "annual_km": 12_345}
    first = client.get("/api/compare", params=params)
    second = client.get("/api/compare", params=params)
    assert first.status_code == 200
    assert first.json() == second.json()


# --- Hand-made vehicles (monkeypatch) -----------------------------------------


def test_electric_and_petrol_costs(fake_catalog) -> None:
    fake_catalog(
        _vehicle(
            1,
            fuel_type="electric",
            transmission="automatic",
            consumption_l_100km=None,
            consumption_kwh_100km=15.3,
        ),
        _vehicle(2, fuel_type="petrol", consumption_l_100km=6.1),
    )
    km = 17_500
    response = _get("1,2", annual_km=km)
    assert response.status_code == 200
    costs = {v["id"]: v["annual_cost_try"] for v in response.json()["vehicles"]}
    ev_price = DEFAULT_ENERGY_PRICES.electricity_per_kwh
    petrol_price = DEFAULT_ENERGY_PRICES.petrol_per_l
    assert costs[1] == _round(km / 100 * 15.3 * ev_price)
    assert costs[2] == _round(km / 100 * 6.1 * petrol_price)


def test_hybrid_uses_petrol_price(fake_catalog) -> None:
    fake_catalog(
        _vehicle(1, fuel_type="hybrid", consumption_l_100km=4.5),
        _vehicle(2, fuel_type="diesel", consumption_l_100km=4.5),
    )
    response = _get("1,2")
    costs = {v["id"]: v["annual_cost_try"] for v in response.json()["vehicles"]}
    km = DEFAULT_ANNUAL_KM
    petrol_price = DEFAULT_ENERGY_PRICES.petrol_per_l
    diesel_price = DEFAULT_ENERGY_PRICES.diesel_per_l
    assert costs[1] == _round(km / 100 * 4.5 * petrol_price)
    assert costs[2] == _round(km / 100 * 4.5 * diesel_price)


def test_custom_petrol_price_changes_cost(fake_catalog) -> None:
    fake_catalog(_vehicle(1), _vehicle(2, fuel_type="diesel"))
    default = _get("1,2").json()
    custom_price = 100.0
    custom = _get("1,2", petrol_price_try=custom_price).json()
    assumptions = custom["assumptions"]
    assert assumptions["petrol_price_try"] == custom_price
    assert assumptions["diesel_price_try"] == DEFAULT_ENERGY_PRICES.diesel_per_l
    default_costs = [v["annual_cost_try"] for v in default["vehicles"]]
    custom_costs = [v["annual_cost_try"] for v in custom["vehicles"]]
    assert custom_costs[0] == _round(DEFAULT_ANNUAL_KM / 100 * 6.0 * custom_price)
    assert custom_costs[0] != default_costs[0]
    # The diesel vehicle does not depend on the petrol price.
    assert custom_costs[1] == default_costs[1]


def test_missing_consumption_gives_null_cost(fake_catalog) -> None:
    fake_catalog(_vehicle(1, consumption_l_100km=None), _vehicle(2))
    response = client.get("/api/compare", params={"ids": "1,2"})
    assert response.status_code == 200
    vehicles = _by_id(response.json())
    assert vehicles[1]["annual_cost_try"] is None
    assert vehicles[2]["annual_cost_try"] is not None


def test_zero_km_and_missing_consumption_stays_null(fake_catalog) -> None:
    fake_catalog(_vehicle(1, consumption_l_100km=None), _vehicle(2))
    response = client.get("/api/compare", params={"ids": "1,2", "annual_km": 0})
    vehicles = _by_id(response.json())
    assert vehicles[1]["annual_cost_try"] is None
    assert vehicles[2]["annual_cost_try"] == 0


def test_differences_cheapest_vehicle(fake_catalog) -> None:
    fake_catalog(
        _vehicle(1, price_try=2_000_000, power_hp=150),
        _vehicle(2, price_try=1_400_000, power_hp=None),
        _vehicle(3, price_try=1_800_000, power_hp=120),
    )
    differences = _differences("1,2,3")
    assert differences["price_try"] == [2]
    assert differences["power_hp"] == [1]
    # Same seats everywhere: no winner.
    assert differences["seats"] == []


def test_differences_tie_lists_all_best(fake_catalog) -> None:
    fake_catalog(
        _vehicle(1, price_try=1_400_000),
        _vehicle(2, price_try=1_400_000),
        _vehicle(3, price_try=1_800_000),
    )
    differences = _differences("1,2,3")
    assert differences["price_try"] == [1, 2]


def test_differences_all_equal_is_empty(fake_catalog) -> None:
    fake_catalog(_vehicle(1), _vehicle(2), _vehicle(3))
    differences = _differences("1,2,3")
    assert differences["price_try"] == []
    assert set(differences) == DIFFERENCE_FIELDS


def test_differences_skip_missing_values(fake_catalog) -> None:
    fake_catalog(
        _vehicle(1, trunk_l=None, euro_ncap_stars=None),
        _vehicle(2, trunk_l=400, euro_ncap_stars=None),
        _vehicle(3, trunk_l=None, euro_ncap_stars=5),
    )
    differences = _differences("1,2,3")
    # Fewer than two vehicles have a value: no winner.
    assert differences["trunk_l"] == []
    assert differences["euro_ncap_stars"] == []


# --- parse_ids unit tests -----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1, 2", [1, 2]), ("1,2,3", [1, 2, 3]), (" 3 ,1 ", [3, 1])],
)
def test_parse_ids_valid(raw: str, expected: list[int]) -> None:
    assert parse_ids(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "1", "1,2,3,4", "1,1", "1,abc", "1,,2", "0,1", "-1,2", "1.5,2", "1,2,"],
)
def test_parse_ids_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_ids(raw)
