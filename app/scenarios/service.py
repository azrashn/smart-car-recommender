"""Scenario re-ranking service (T50, M6).

Reuses M3 (``generate_recommendations``) and M5's cost calculator
(``app.cost.calculator``); it does not duplicate scoring or cost formulas.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

from app.cost.calculator import EnergyPrices, annual_cost_for_vehicle
from app.engine.service import generate_recommendations, load_catalog_vehicles
from app.scenarios.schemas import (
    ScenarioItem,
    ScenarioOverrides,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioResult,
)
from app.schemas.preference import Preference, ScoringPriorities
from app.schemas.recommendation import ConflictReport
from app.schemas.vehicle import Vehicle

# --- Defaults (assumptions; overridable per request) -----------------------------
# Istanbul (European side) pump prices incl. VAT on 17 Nov 2026 (Dünya, Petrol Ofisi list).
DEFAULT_PETROL_PER_L = 71.20
DEFAULT_DIESEL_PER_L = 95.20
# Public AC charging average, about 8.5 TRY/kWh (Sözcü, Jan 2026). Home tariffs differ.
DEFAULT_ELECTRICITY_PER_KWH = 8.50
# Used only when neither the preference nor the overrides give an annual mileage.
DEFAULT_ANNUAL_KM = 15_000


def merge_priorities(base: ScoringPriorities, override) -> ScoringPriorities:
    """Apply a partial override on top of the base priorities (unset keys keep the base)."""
    if override is None:
        return base
    changes = {k: v for k, v in override.model_dump().items() if v is not None}
    return base.model_copy(update=changes)


def build_prices(fuel_price_try: Optional[float]) -> EnergyPrices:
    """Energy prices for the scenario. A petrol override scales diesel by the default ratio."""
    petrol = fuel_price_try if fuel_price_try is not None else DEFAULT_PETROL_PER_L
    diesel = petrol * (DEFAULT_DIESEL_PER_L / DEFAULT_PETROL_PER_L)
    return EnergyPrices(
        petrol_per_l=petrol,
        diesel_per_l=diesel,
        electricity_per_kwh=DEFAULT_ELECTRICITY_PER_KWH,
    )


def _cost_for(vehicle: Vehicle, annual_km: int, prices: EnergyPrices) -> Optional[float]:
    cost = annual_cost_for_vehicle(
        vehicle.fuel_type,
        annual_km,
        vehicle.consumption_l_100km,
        vehicle.consumption_kwh_100km,
        prices,
    )
    return None if cost is None else round(cost, 2)


def run_scenario(
    request: ScenarioRequest,
    vehicles: Optional[Sequence[Vehicle]] = None,
) -> ScenarioResponse:
    """Re-run the recommendation engine with the overrides and compare with the base run."""
    pool = list(vehicles) if vehicles is not None else load_catalog_vehicles()
    by_id: Dict[int, Vehicle] = {v.id: v for v in pool}
    overrides: ScenarioOverrides = request.overrides

    base_pref: Preference = request.preference
    scenario_pref = base_pref.model_copy(
        update={"priorities": merge_priorities(base_pref.priorities, overrides.priorities)}
    )

    scenario = generate_recommendations(scenario_pref, pool)
    if isinstance(scenario, ConflictReport):
        return scenario

    base = generate_recommendations(base_pref, pool)
    base_ranks: Dict[int, int] = (
        {} if isinstance(base, ConflictReport) else {r.vehicle_id: r.rank for r in base.recommendations}
    )

    annual_km = overrides.annual_km or base_pref.annual_km or DEFAULT_ANNUAL_KM
    prices = build_prices(overrides.fuel_price_try)

    items = []
    for rec in scenario.recommendations:
        base_rank = base_ranks.get(rec.vehicle_id)
        data = rec.model_dump()
        data["estimated_annual_cost_try"] = _cost_for(by_id[rec.vehicle_id], annual_km, prices)
        data["base_rank"] = base_rank
        data["rank_change"] = None if base_rank is None else base_rank - rec.rank
        items.append(ScenarioItem(**data))

    return ScenarioResult(
        total_matches=scenario.total_matches,
        recommendations=items,
        applied_filters=scenario.applied_filters,
        weights_used=scenario.weights_used,
        annual_km_used=annual_km,
        fuel_price_try_used=round(prices.petrol_per_l, 2),
        electricity_price_try_used=prices.electricity_per_kwh,
    )
