"""Default assumptions for the annual energy cost (M5, FR-11)."""

from __future__ import annotations

import datetime as dt

from app.cost.calculator import EnergyPrices

# These are example values only. Energy prices change quickly and these numbers
# go stale fast. The UI shows them as "example price, checked on <date>".
DEFAULT_ANNUAL_KM = 15_000
DEFAULT_ENERGY_PRICES = EnergyPrices(
    petrol_per_l=68.43,
    diesel_per_l=84.60,
    electricity_per_kwh=9.95,
)
PRICES_CHECKED_AT = dt.date(2026, 11, 27)
