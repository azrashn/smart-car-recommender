"""Annual energy cost calculation (T40, FR-11).

Pure and deterministic: no database, no I/O, no rounding (NFR-01, NFR-07).
Round only at the presentation layer.

Formula:
    annual_cost = annual_km / 100 * consumption_per_100km * unit_price

    - combustion and hybrid: consumption in L/100 km, price in TRY per litre
    - electric:              consumption in kWh/100 km, price in TRY per kWh

Missing consumption data is never estimated (NFR-04): the result is None.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

ELECTRIC = "electric"
FUEL_TYPES = frozenset({"petrol", "diesel", "hybrid"})


@dataclass(frozen=True)
class EnergyPrices:
    """Energy prices used for the cost calculation (TRY)."""

    petrol_per_l: float
    diesel_per_l: float
    electricity_per_kwh: float

    def __post_init__(self) -> None:
        _require_non_negative("petrol_per_l", self.petrol_per_l)
        _require_non_negative("diesel_per_l", self.diesel_per_l)
        _require_non_negative("electricity_per_kwh", self.electricity_per_kwh)


def _require_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite number >= 0, got {value!r}")


def _normalize_fuel_type(fuel_type: object) -> str:
    # Accepts plain strings and str-based enums (e.g. FuelType.petrol).
    value = getattr(fuel_type, "value", fuel_type)
    if value != ELECTRIC and value not in FUEL_TYPES:
        raise ValueError(f"unsupported fuel_type: {fuel_type!r}")
    return value


def annual_energy_cost(
    annual_km: float,
    consumption_per_100km: float | None,
    unit_price: float,
) -> float | None:
    """Core formula shared by fuel (L) and electric (kWh) vehicles.

    Returns None if consumption is missing. 0 km returns 0.0.
    Raises ValueError for negative or non-finite inputs, or consumption <= 0.
    """
    _require_non_negative("annual_km", annual_km)
    _require_non_negative("unit_price", unit_price)
    if consumption_per_100km is None:
        return None
    if not math.isfinite(consumption_per_100km) or consumption_per_100km <= 0:
        raise ValueError(
            f"consumption_per_100km must be a finite number > 0, got {consumption_per_100km!r}"
        )
    return annual_km / 100 * consumption_per_100km * unit_price


def unit_price_for(fuel_type: object, prices: EnergyPrices) -> float:
    """Pick the price that matches the vehicle's energy source."""
    kind = _normalize_fuel_type(fuel_type)
    if kind == ELECTRIC:
        return prices.electricity_per_kwh
    if kind == "diesel":
        return prices.diesel_per_l
    return prices.petrol_per_l  # petrol and hybrid (assumption, see PR notes)


def annual_cost_for_vehicle(
    fuel_type: object,
    annual_km: float,
    consumption_l_100km: float | None,
    consumption_kwh_100km: float | None,
    prices: EnergyPrices,
) -> float | None:
    """Annual energy cost for one catalogue vehicle.

    Electric vehicles use consumption_kwh_100km; all others use
    consumption_l_100km. The unused column is ignored.
    """
    consumption = (
        consumption_kwh_100km
        if _normalize_fuel_type(fuel_type) == ELECTRIC
        else consumption_l_100km
    )
    return annual_energy_cost(annual_km, consumption, unit_price_for(fuel_type, prices))
