"""FastAPI router for M5 (Comparison) - T42.

Endpoint:
GET /api/compare?ids=1,2,3
Returns: CompareResponse (2-3 vehicles side by side with annual energy cost)
Errors: 422 for invalid ids or query values, 404 for unknown vehicle IDs.
"""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException, Query

from app.compare import service
from app.compare.schemas import CompareResponse
from app.cost.defaults import DEFAULT_ANNUAL_KM, DEFAULT_ENERGY_PRICES

router = APIRouter(prefix="/api", tags=["compare"])


@router.get(
    "/compare",
    response_model=CompareResponse,
    summary="Compare 2-3 vehicles side by side with estimated annual energy cost",
)
def get_compare(
    ids: str = Query(..., description="Comma-separated vehicle IDs, 2-3 IDs"),
    annual_km: int = Query(DEFAULT_ANNUAL_KM, ge=0, le=1_000_000),
    petrol_price_try: float | None = Query(None, ge=0, le=10_000),
    diesel_price_try: float | None = Query(None, ge=0, le=10_000),
    electricity_price_try: float | None = Query(None, ge=0, le=10_000),
) -> CompareResponse:
    """Return the requested vehicles in request order, their annual energy cost,
    the best vehicle per unit-independent field and the assumptions used."""
    try:
        vehicle_ids = service.parse_ids(ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    overrides: dict[str, float] = {}
    if petrol_price_try is not None:
        overrides["petrol_per_l"] = petrol_price_try
    if diesel_price_try is not None:
        overrides["diesel_per_l"] = diesel_price_try
    if electricity_price_try is not None:
        overrides["electricity_per_kwh"] = electricity_price_try
    prices = dataclasses.replace(DEFAULT_ENERGY_PRICES, **overrides)

    try:
        return service.build_comparison(vehicle_ids, annual_km, prices)
    except service.MissingVehiclesError as exc:
        raise HTTPException(
            status_code=404, detail=f"Vehicles not found: {sorted(exc.missing_ids)}"
        ) from exc
