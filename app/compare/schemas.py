"""Response models for GET /api/compare (M5, T42).

These models are specific to the compare module; they are not shared schemas.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class CompareVehicle(BaseModel):
    """One vehicle in the comparison, with its estimated annual energy cost."""

    id: int
    brand: str
    model: str
    variant: str
    year: int
    body_type: str
    fuel_type: str
    transmission: str
    price_try: int
    price_checked_at: dt.date
    consumption_l_100km: float | None = None
    consumption_kwh_100km: float | None = None
    power_hp: int | None = None
    seats: int
    trunk_l: int | None = None
    euro_ncap_stars: int | None = None
    spec_source_url: str
    price_source_url: str
    annual_cost_try: int | None = Field(
        None,
        description="Rounded annual energy cost (TRY); null if consumption is missing.",
    )


class CompareAssumptions(BaseModel):
    """Inputs actually used for the annual cost calculation."""

    annual_km: int
    petrol_price_try: float
    diesel_price_try: float
    electricity_price_try: float
    prices_checked_at: dt.date


class CompareResponse(BaseModel):
    """Response body of GET /api/compare."""

    vehicles: list[CompareVehicle]
    differences: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Field name -> IDs of the vehicles with the best value.",
    )
    assumptions: CompareAssumptions
