"""Tests for the annual energy cost calculator (T41, FR-11).

Formula under test:
    annual_cost = annual_km / 100 * consumption_per_100km * unit_price

All tests are pure function calls: no database, no files, no network.
"""

from __future__ import annotations

import dataclasses
import math
from enum import Enum

import pytest

from app.cost.calculator import (
    EnergyPrices,
    annual_cost_for_vehicle,
    annual_energy_cost,
    unit_price_for,
)

NAN = float("nan")
INF = float("inf")

# Distinct prices so that every price selection can be told apart.
PRICES = EnergyPrices(petrol_per_l=50.0, diesel_per_l=45.0, electricity_per_kwh=5.0)


class FuelKind(str, Enum):
    """Local str-based enum, mirrors how a schema enum would be passed in."""

    petrol = "petrol"
    diesel = "diesel"
    hybrid = "hybrid"
    electric = "electric"


class PlainKind(Enum):  # not a str subclass: forces the .value path
    petrol = "petrol"
    diesel = "diesel"
    hybrid = "hybrid"
    electric = "electric"


# --------------------------------------------------------------------------
# Known inputs (acceptance criterion 1 and real data)
# --------------------------------------------------------------------------


def test_documented_example_fuel_vehicle():
    # Documented example: 12,000 km, 5.2 L/100 km, 50 TRY/L -> 31,200 TRY.
    assert annual_energy_cost(12_000, 5.2, 50.0) == pytest.approx(31_200.0)


def test_documented_example_via_vehicle_function():
    # Same documented example through the per-vehicle entry point (petrol price).
    result = annual_cost_for_vehicle("petrol", 12_000, 5.2, None, PRICES)
    assert result == pytest.approx(31_200.0)


def test_electric_vehicle_uses_kwh_and_electricity_price():
    # EV: 12,000 km, 16 kWh/100 km, 5 TRY/kWh -> 9,600 TRY.
    result = annual_cost_for_vehicle("electric", 12_000, None, 16.0, PRICES)
    assert result == pytest.approx(9_600.0)


def test_hybrid_uses_litres_and_ignores_kwh():
    # hybrid uses L/100km only, by design: the kWh value is ignored and the
    # petrol price is applied (12,000 km, 5.2 L/100 km, 50 TRY/L -> 31,200 TRY).
    result = annual_cost_for_vehicle("hybrid", 12_000, 5.2, 16.0, PRICES)
    assert result == pytest.approx(31_200.0)


def test_real_data_corolla_hybrid_dream():
    # Real catalogue row (data/vehicles.csv id 32, Toyota Corolla 1.8 Hybrid Dream,
    # 4.5 L/100 km, no kWh value): 15,000 km at 47 TRY/L -> 31,725 TRY.
    # Values are inlined on purpose so the test stays a pure function call.
    prices = EnergyPrices(petrol_per_l=47.0, diesel_per_l=45.0, electricity_per_kwh=5.0)
    result = annual_cost_for_vehicle("hybrid", 15_000, 4.5, None, prices)
    assert result == pytest.approx(31_725.0)


# --------------------------------------------------------------------------
# Boundary values
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("annual_km", "expected"),
    [
        (0, 0.0),
        (1, 2.6),
        (100, 260.0),
    ],
)
def test_boundary_km_values(annual_km, expected):
    # 0 km costs nothing; 1 km and 100 km follow the formula exactly (5.2 L, 50 TRY/L).
    assert annual_energy_cost(annual_km, 5.2, 50.0) == pytest.approx(expected)


def test_very_large_km_is_finite_and_exact():
    # 10,000,000 km must not overflow to inf and must match the formula.
    result = annual_energy_cost(10_000_000, 5.2, 50.0)
    assert math.isfinite(result)
    # 10,000,000 / 100 * 5.2 * 50 = 26,000,000
    assert result == pytest.approx(26_000_000.0)


@pytest.mark.parametrize("fuel_type", ["petrol", "diesel", "hybrid", "electric"])
def test_zero_price_gives_zero_cost(fuel_type):
    # A zero unit price is valid and yields a cost of exactly 0 for every fuel type.
    free = EnergyPrices(petrol_per_l=0.0, diesel_per_l=0.0, electricity_per_kwh=0.0)
    result = annual_cost_for_vehicle(fuel_type, 12_000, 5.2, 16.0, free)
    assert result == pytest.approx(0.0)


def test_zero_price_core_formula():
    # Core formula: zero unit price -> zero cost.
    assert annual_energy_cost(12_000, 5.2, 0.0) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# Missing data (NFR-04: never estimated)
# --------------------------------------------------------------------------


def test_missing_consumption_returns_none():
    # Missing consumption is not estimated: the core formula returns None.
    assert annual_energy_cost(12_000, None, 50.0) is None


@pytest.mark.parametrize("fuel_type", ["petrol", "diesel", "hybrid", "electric"])
def test_vehicle_missing_consumption_returns_none(fuel_type):
    # A vehicle with no consumption data at all gets None, not an estimate.
    result = annual_cost_for_vehicle(fuel_type, 12_000, None, None, PRICES)
    assert result is None


def test_zero_km_with_missing_consumption_returns_none():
    # 0 km is valid, so missing consumption still yields None rather than 0.
    assert annual_energy_cost(0, None, 50.0) is None


@pytest.mark.parametrize(
    ("fuel_type", "consumption_l", "consumption_kwh"),
    [
        # EV with only a litre value: the kWh column is empty -> None.
        ("electric", 5.2, None),
        # Combustion and hybrid vehicles with only a kWh value -> None.
        ("petrol", None, 16.0),
        ("diesel", None, 16.0),
        ("hybrid", None, 16.0),
    ],
)
def test_wrong_unit_column_returns_none(fuel_type, consumption_l, consumption_kwh):
    # Wrong unit column filled: the other column is never used as a fallback (NFR-04).
    result = annual_cost_for_vehicle(fuel_type, 12_000, consumption_l, consumption_kwh, PRICES)
    assert result is None


# --------------------------------------------------------------------------
# Invalid inputs
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [-1.0, -0.01, NAN, INF, -INF])
@pytest.mark.parametrize("argument", ["annual_km", "unit_price"])
def test_invalid_km_or_price_raises(argument, bad_value):
    # Negative or non-finite km and unit price are rejected with ValueError.
    kwargs = {"annual_km": 12_000, "consumption_per_100km": 5.2, "unit_price": 50.0}
    kwargs[argument] = bad_value
    with pytest.raises(ValueError, match=argument):
        annual_energy_cost(**kwargs)


@pytest.mark.parametrize("bad_consumption", [0.0, -1.0, -5.2, NAN, INF, -INF])
def test_invalid_consumption_raises(bad_consumption):
    # Zero, negative or non-finite consumption is rejected (only None means "missing").
    with pytest.raises(ValueError, match="consumption_per_100km"):
        annual_energy_cost(12_000, bad_consumption, 50.0)


@pytest.mark.parametrize(
    ("annual_km", "unit_price", "argument"),
    [
        (-1.0, 50.0, "annual_km"),
        (12_000, -1.0, "unit_price"),
        (NAN, 50.0, "annual_km"),
    ],
)
def test_validation_runs_before_missing_consumption_check(annual_km, unit_price, argument):
    # Validation order: invalid km or price raises even when consumption is None.
    with pytest.raises(ValueError, match=argument):
        annual_energy_cost(annual_km, None, unit_price)


@pytest.mark.parametrize("bad_value", [NAN, INF, -INF, -1.0, -0.01])
@pytest.mark.parametrize("field", ["petrol_per_l", "diesel_per_l", "electricity_per_kwh"])
def test_energy_prices_rejects_invalid_values(field, bad_value):
    # Every price field rejects nan, +/-inf and negative values at construction time.
    values = {"petrol_per_l": 50.0, "diesel_per_l": 45.0, "electricity_per_kwh": 5.0}
    values[field] = bad_value
    with pytest.raises(ValueError, match=field):
        EnergyPrices(**values)


def test_energy_prices_accepts_zero():
    # Zero prices are valid (lower bound is inclusive).
    prices = EnergyPrices(petrol_per_l=0.0, diesel_per_l=0.0, electricity_per_kwh=0.0)
    assert prices.petrol_per_l == pytest.approx(0.0)
    assert prices.diesel_per_l == pytest.approx(0.0)
    assert prices.electricity_per_kwh == pytest.approx(0.0)


@pytest.mark.parametrize("fuel_type", ["lpg", "", None, 123])
def test_unsupported_fuel_type_raises(fuel_type):
    # Unknown fuel types are rejected by both public functions that take fuel_type.
    with pytest.raises(ValueError, match="unsupported fuel_type"):
        unit_price_for(fuel_type, PRICES)
    with pytest.raises(ValueError, match="unsupported fuel_type"):
        annual_cost_for_vehicle(fuel_type, 12_000, 5.2, 16.0, PRICES)


@pytest.mark.parametrize("fuel_type", ["Electric", "ELECTRIC", "Petrol", "DIESEL", "Hybrid"])
def test_fuel_type_is_case_sensitive(fuel_type):
    # The calculator does not normalise case. Enum values are lower case by contract
    # (docs/api-contract.md section 1), so mixed or upper case is rejected with ValueError.
    with pytest.raises(ValueError, match="unsupported fuel_type"):
        unit_price_for(fuel_type, PRICES)
    with pytest.raises(ValueError, match="unsupported fuel_type"):
        annual_cost_for_vehicle(fuel_type, 12_000, 5.2, 16.0, PRICES)


def test_unused_litre_column_nan_is_ignored_for_ev():
    # For an EV the litre column is never read, so nan there must not raise.
    result = annual_cost_for_vehicle("electric", 12_000, NAN, 16.0, PRICES)
    assert result == pytest.approx(9_600.0)


@pytest.mark.parametrize(
    ("fuel_type", "expected"),
    [
        ("petrol", 31_200.0),
        ("hybrid", 31_200.0),
        ("diesel", 28_080.0),  # 12,000 / 100 * 5.2 * 45
    ],
)
def test_unused_kwh_column_nan_is_ignored_for_fuel_vehicles(fuel_type, expected):
    # For combustion and hybrid vehicles the kWh column is never read; the cost is exact.
    result = annual_cost_for_vehicle(fuel_type, 12_000, 5.2, NAN, PRICES)
    assert result == pytest.approx(expected)


def test_vehicle_negative_km_raises():
    # The per-vehicle entry point propagates km validation from the core formula.
    with pytest.raises(ValueError, match="annual_km"):
        annual_cost_for_vehicle("electric", -1, None, 16.0, PRICES)


def test_vehicle_zero_consumption_raises():
    # Zero consumption in the column that is used is rejected, not treated as missing.
    with pytest.raises(ValueError, match="consumption_per_100km"):
        annual_cost_for_vehicle("electric", 12_000, None, 0.0, PRICES)


# --------------------------------------------------------------------------
# Price selection (unit_price_for)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fuel_type", "expected_price"),
    [
        ("petrol", 50.0),
        ("hybrid", 50.0),  # hybrid shares petrol_per_l with petrol
        ("diesel", 45.0),
        ("electric", 5.0),
    ],
)
def test_unit_price_for_selects_matching_price(fuel_type, expected_price):
    # Each fuel type picks its own price field; petrol and hybrid both use petrol_per_l.
    assert unit_price_for(fuel_type, PRICES) == pytest.approx(expected_price)


def test_petrol_and_hybrid_share_price_diesel_differs():
    # petrol and hybrid select the same price; diesel selects diesel_per_l.
    assert unit_price_for("petrol", PRICES) == pytest.approx(unit_price_for("hybrid", PRICES))
    assert unit_price_for("diesel", PRICES) == pytest.approx(PRICES.diesel_per_l)
    assert unit_price_for("diesel", PRICES) != pytest.approx(unit_price_for("petrol", PRICES))


@pytest.mark.parametrize(
    ("fuel_type", "expected_price"),
    [
        (FuelKind.petrol, 50.0),
        (FuelKind.hybrid, 50.0),
        (FuelKind.diesel, 45.0),
        (FuelKind.electric, 5.0),
    ],
)
def test_unit_price_for_accepts_str_enum(fuel_type, expected_price):
    # str-based enums are accepted through their .value.
    assert unit_price_for(fuel_type, PRICES) == pytest.approx(expected_price)


@pytest.mark.parametrize(
    ("fuel_type", "expected"),
    [
        ("diesel", 28_080.0),
        (FuelKind.diesel, 28_080.0),
        (FuelKind.electric, 9_600.0),
    ],
)
def test_vehicle_cost_uses_selected_price(fuel_type, expected):
    # The per-vehicle cost combines the right consumption column with the right price.
    result = annual_cost_for_vehicle(fuel_type, 12_000, 5.2, 16.0, PRICES)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("fuel_type", "expected_price"),
    [
        (PlainKind.petrol, 50.0),
        (PlainKind.hybrid, 50.0),
        (PlainKind.diesel, 45.0),
        (PlainKind.electric, 5.0),
    ],
)
def test_unit_price_for_accepts_plain_enum(fuel_type, expected_price):
    # Non-str enums are accepted through their .value attribute.
    assert unit_price_for(fuel_type, PRICES) == pytest.approx(expected_price)


def test_vehicle_cost_accepts_plain_enum():
    # A non-str enum selects the kWh column and electricity price for an EV.
    result = annual_cost_for_vehicle(PlainKind.electric, 12_000, None, 16.0, PRICES)
    assert result == pytest.approx(9_600.0)


# --------------------------------------------------------------------------
# Properties
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda: annual_energy_cost(12_345, 5.55, 33.33),
        lambda: annual_cost_for_vehicle("electric", 12_345, None, 16.4, PRICES),
        lambda: annual_cost_for_vehicle("hybrid", 12_345, 4.5, None, PRICES),
    ],
)
def test_determinism(call):
    # Ten calls with the same input return exactly the same value.
    results = [call() for _ in range(10)]
    assert all(r == pytest.approx(results[0], rel=0, abs=0) for r in results)


@pytest.mark.parametrize("annual_km", [1, 7_500, 12_000, 33_333])
def test_linearity_in_km(annual_km):
    # Doubling the yearly distance doubles the cost.
    single = annual_energy_cost(annual_km, 5.2, 50.0)
    double = annual_energy_cost(annual_km * 2, 5.2, 50.0)
    assert double == pytest.approx(2 * single)


def test_no_rounding():
    # Full precision is kept: 1 km, 5.55 L/100 km, 33.33 TRY/L equals the raw formula.
    expected = 1 / 100 * 5.55 * 33.33
    result = annual_energy_cost(1, 5.55, 33.33)
    assert result == pytest.approx(expected, rel=0, abs=0)
    # The raw value has more than two decimals, so a rounded result would differ.
    assert result != pytest.approx(round(expected, 2), rel=0, abs=0)


@pytest.mark.parametrize("fuel_type", ["petrol", "diesel", "hybrid", "electric"])
def test_purity_prices_unchanged(fuel_type):
    # The prices object is identical before and after the call (no mutation).
    prices = EnergyPrices(petrol_per_l=50.0, diesel_per_l=45.0, electricity_per_kwh=5.0)
    snapshot = dataclasses.asdict(prices)
    annual_cost_for_vehicle(fuel_type, 12_000, 5.2, 16.0, prices)
    unit_price_for(fuel_type, prices)
    assert dataclasses.asdict(prices) == snapshot


def test_energy_prices_is_frozen():
    # EnergyPrices is immutable, so callers cannot change prices after creation.
    with pytest.raises(dataclasses.FrozenInstanceError):
        PRICES.petrol_per_l = 1.0  # type: ignore[misc]
