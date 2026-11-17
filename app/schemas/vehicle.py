"""Vehicle schema for M1 (Vehicle Data & Catalogue): shared contract across all modules.

One ``Vehicle`` equals one row of ``data/vehicles.csv``. Field names, order, units and
allowed values are documented in ``docs/data-dictionary.md``.

This schema is consumed by:
- T04  : CSV validation and seed script (CSV -> SQLite)
- T05  : GET /api/vehicles and GET /api/vehicles/{id} responses
- M3   : hard-constraint filters and weighted scoring
- M5   : annual energy cost and side-by-side comparison
- M6   : Scenario Lab recalculation

Design rules
------------
- Pydantic v2, ``extra="forbid"``: an unknown column is an error, not silently dropped.
- Missing data is never guessed (NFR-04): optional fields are ``None`` and an empty
  CSV cell is read as ``None``. Scoring excludes criteria whose data is ``None``.
- Enum values are stored as plain strings (``use_enum_values``) so that
  ``app/engine/filters.py`` can compare them directly.
- ``from_attributes=True`` lets T05 build a ``Vehicle`` from a SQLAlchemy row.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.preference import BodyType, FuelType

Transmission = Literal["manual", "automatic"]

_Url = Annotated[str, Field(pattern=r"^https?://\S+$", max_length=500)]

# Column order of data/vehicles.csv. Must stay identical to the Vehicle fields below.
VEHICLE_CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "brand",
    "model",
    "variant",
    "year",
    "body_type",
    "fuel_type",
    "transmission",
    "consumption_l_100km",
    "consumption_kwh_100km",
    "range_km",
    "power_hp",
    "seats",
    "trunk_l",
    "euro_ncap_stars",
    "price_try",
    "price_checked_at",
    "spec_source_url",
    "price_source_url",
)

_OPTIONAL_FIELDS = (
    "consumption_l_100km",
    "consumption_kwh_100km",
    "range_km",
    "power_hp",
    "trunk_l",
    "euro_ncap_stars",
)


class Vehicle(BaseModel):
    """A single vehicle variant from the catalogue (one row of data/vehicles.csv)."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )

    # --- Identity ---
    id: int = Field(..., ge=1, description="Stable catalogue ID; never reused.")
    brand: str = Field(..., min_length=1, max_length=50, description="Brand, e.g. Toyota.")
    model: str = Field(..., min_length=1, max_length=50, description="Model, e.g. Corolla.")
    variant: str = Field(
        ..., min_length=1, max_length=100, description="Engine and trim, e.g. 1.8 Hybrid Dream."
    )
    year: int = Field(..., ge=2000, le=2100, description="Model year.")

    # --- Categories (hard filters) ---
    body_type: BodyType = Field(..., description="hatchback, sedan, suv, wagon or mpv.")
    fuel_type: FuelType = Field(..., description="petrol, diesel, hybrid or electric.")
    transmission: Transmission = Field(..., description="manual or automatic.")

    # --- Energy (WLTP combined) ---
    consumption_l_100km: float | None = Field(
        None, gt=0, le=30, description="Fuel use in L/100 km. Empty for electric."
    )
    consumption_kwh_100km: float | None = Field(
        None, gt=0, le=50, description="Energy use in kWh/100 km. Electric only."
    )
    range_km: int | None = Field(None, gt=0, le=1500, description="Electric range in km.")

    # --- Specs used for scoring ---
    power_hp: int | None = Field(None, gt=0, le=2000, description="Power in PS (metric hp).")
    seats: int = Field(..., ge=2, le=9, description="Number of seats.")
    trunk_l: int | None = Field(None, gt=0, le=3000, description="Boot volume in litres.")
    euro_ncap_stars: int | None = Field(
        None, ge=0, le=5, description="Euro NCAP rating (0-5). Empty if not tested."
    )

    # --- Price and provenance ---
    price_try: int = Field(..., gt=0, description="Example list price in TRY.")
    price_checked_at: dt.date = Field(..., description="Date the price was checked.")
    spec_source_url: _Url = Field(..., description="Official page for technical specs.")
    price_source_url: _Url = Field(..., description="Official page for the price.")

    @field_validator(*_OPTIONAL_FIELDS, mode="before")
    @classmethod
    def _empty_cell_to_none(cls, value: object) -> object:
        """Read an empty CSV cell as missing data instead of failing to parse it."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _energy_fields_match_fuel_type(self) -> Vehicle:
        """Reject energy values that make no sense for the vehicle's fuel type."""
        if self.fuel_type == FuelType.electric.value:
            if self.consumption_l_100km is not None:
                raise ValueError("electric vehicles must leave consumption_l_100km empty")
        else:
            for field_name in ("consumption_kwh_100km", "range_km"):
                if getattr(self, field_name) is not None:
                    raise ValueError(f"{field_name} is only allowed for electric vehicles")
        return self


class VehicleListResponse(BaseModel):
    """Response body of GET /api/vehicles."""

    total: int = Field(..., ge=0, description="Number of vehicles matching the filters.")
    items: list[Vehicle] = Field(default_factory=list, description="Vehicles on this page.")
