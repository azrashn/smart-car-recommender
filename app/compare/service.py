"""Comparison service for GET /api/compare (M5, T42, FR-10, FR-11).

Pure and deterministic (NFR-01): the same IDs and inputs always give the same
response. Rounding happens only here, at the presentation layer.
"""

from __future__ import annotations

import math

from app.compare.schemas import CompareAssumptions, CompareResponse, CompareVehicle
from app.cost.calculator import EnergyPrices, annual_cost_for_vehicle
from app.cost.defaults import PRICES_CHECKED_AT
from app.engine.service import load_catalog_vehicles
from app.schemas.vehicle import Vehicle

MIN_IDS = 2
MAX_IDS = 3

# Unit-independent fields only. Consumption (L vs kWh) is never compared.
LOWER_IS_BETTER: tuple[str, ...] = ("price_try", "annual_cost_try")
HIGHER_IS_BETTER: tuple[str, ...] = ("power_hp", "trunk_l", "seats", "euro_ncap_stars")


class MissingVehiclesError(Exception):
    """Raised when one or more requested vehicle IDs are not in the catalogue."""

    def __init__(self, missing_ids: list[int]) -> None:
        self.missing_ids = missing_ids
        super().__init__(f"Vehicles not found: {sorted(missing_ids)}")


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def get_vehicles_by_ids(ids: list[int]) -> list[Vehicle]:
    """Return catalogue vehicles in the same order as ``ids``.

    Raises MissingVehiclesError if any ID is not found.

    When T05 (catalogue service) is merged, only the body of this function changes.
    """
    by_id = {vehicle.id: vehicle for vehicle in load_catalog_vehicles()}
    missing = [vehicle_id for vehicle_id in ids if vehicle_id not in by_id]
    if missing:
        raise MissingVehiclesError(missing)
    return [by_id[vehicle_id] for vehicle_id in ids]


def parse_ids(raw: str) -> list[int]:
    """Parse a comma-separated ID string such as ``"1, 2, 3"``.

    Raises ValueError for empty input, empty items, non-integers, IDs < 1,
    duplicate IDs, or a count outside 2-3.
    """
    if not raw.strip():
        raise ValueError("ids must not be empty.")
    ids: list[int] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            raise ValueError("ids must not contain empty items.")
        try:
            value = int(item)
        except ValueError:
            raise ValueError(f"ids must be integers, got {item!r}.") from None
        if value < 1:
            raise ValueError(f"ids must be >= 1, got {value}.")
        if value in ids:
            raise ValueError(f"ids must not contain duplicates, got {value} twice.")
        ids.append(value)
    if not MIN_IDS <= len(ids) <= MAX_IDS:
        raise ValueError(f"ids must contain {MIN_IDS} to {MAX_IDS} vehicle IDs.")
    return ids


def _best_ids(
    vehicles: list[CompareVehicle],
    field: str,
    lower_is_better: bool,
) -> list[int]:
    """IDs of the vehicles with the best value for ``field``.

    Vehicles with a missing value are skipped. Returns an empty list when fewer
    than two vehicles have a value or when all values are equal.
    """
    values = [
        (vehicle.id, getattr(vehicle, field))
        for vehicle in vehicles
        if getattr(vehicle, field) is not None
    ]
    if len(values) < 2:
        return []
    distinct = {value for _, value in values}
    if len(distinct) == 1:
        return []
    best = min(distinct) if lower_is_better else max(distinct)
    return [vehicle_id for vehicle_id, value in values if value == best]


def _differences(vehicles: list[CompareVehicle]) -> dict[str, list[int]]:
    differences: dict[str, list[int]] = {}
    for field in LOWER_IS_BETTER:
        differences[field] = _best_ids(vehicles, field, lower_is_better=True)
    for field in HIGHER_IS_BETTER:
        differences[field] = _best_ids(vehicles, field, lower_is_better=False)
    return differences


def _to_compare_vehicle(
    vehicle: Vehicle,
    annual_km: int,
    prices: EnergyPrices,
) -> CompareVehicle:
    cost = annual_cost_for_vehicle(
        vehicle.fuel_type,
        annual_km,
        vehicle.consumption_l_100km,
        vehicle.consumption_kwh_100km,
        prices,
    )
    return CompareVehicle(
        id=vehicle.id,
        brand=vehicle.brand,
        model=vehicle.model,
        variant=vehicle.variant,
        year=vehicle.year,
        body_type=vehicle.body_type,
        fuel_type=vehicle.fuel_type,
        transmission=vehicle.transmission,
        price_try=vehicle.price_try,
        price_checked_at=vehicle.price_checked_at,
        consumption_l_100km=vehicle.consumption_l_100km,
        consumption_kwh_100km=vehicle.consumption_kwh_100km,
        power_hp=vehicle.power_hp,
        seats=vehicle.seats,
        trunk_l=vehicle.trunk_l,
        euro_ncap_stars=vehicle.euro_ncap_stars,
        spec_source_url=vehicle.spec_source_url,
        price_source_url=vehicle.price_source_url,
        annual_cost_try=None if cost is None else _round_half_up(cost),
    )


def build_comparison(
    ids: list[int],
    annual_km: int,
    prices: EnergyPrices,
) -> CompareResponse:
    """Build the side-by-side comparison for the given vehicle IDs.

    Raises MissingVehiclesError if any ID is not in the catalogue.
    """
    catalog_vehicles = get_vehicles_by_ids(ids)
    vehicles = [_to_compare_vehicle(v, annual_km, prices) for v in catalog_vehicles]
    return CompareResponse(
        vehicles=vehicles,
        differences=_differences(vehicles),
        assumptions=CompareAssumptions(
            annual_km=annual_km,
            petrol_price_try=prices.petrol_per_l,
            diesel_price_try=prices.diesel_per_l,
            electricity_price_try=prices.electricity_per_kwh,
            prices_checked_at=PRICES_CHECKED_AT,
        ),
    )
