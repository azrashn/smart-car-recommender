"""Request/response schemas for ``POST /api/scenarios`` (T50).

The request wraps a base ``Preference`` plus optional what-if overrides. The
response mirrors ``RecommendationResult`` and adds rank-change information so the
UI can show "before / after" (T52).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.preference import Preference, Priority
from app.schemas.recommendation import ConflictReport, RecommendationItem


class PriorityOverrides(BaseModel):
    """Partial priority override: keys that are ``None`` keep the base preference value."""

    model_config = {"extra": "forbid"}

    fuel_economy: Optional[Priority] = None
    interior_space: Optional[Priority] = None
    performance: Optional[Priority] = None
    budget_fit: Optional[Priority] = None
    safety: Optional[Priority] = None


class ScenarioOverrides(BaseModel):
    """What-if values. Every field is optional; an empty object reproduces the base run."""

    model_config = {"extra": "forbid"}

    annual_km: Optional[int] = Field(
        None, ge=1_000, le=200_000, description="Annual mileage used for the cost estimate."
    )
    fuel_price_try: Optional[float] = Field(
        None,
        gt=0,
        le=1_000,
        description=(
            "Petrol price in TRY per litre. Hybrid cars use it as-is, diesel keeps its "
            "default ratio to petrol."
        ),
    )
    electricity_price_try: Optional[float] = Field(
        None, gt=0, le=1_000, description="Electricity price in TRY per kWh (electric cars)."
    )
    priorities: Optional[PriorityOverrides] = Field(
        None, description="Partial priority override; unset keys keep the base value."
    )


class ScenarioRequest(BaseModel):
    model_config = {"extra": "forbid"}

    preference: Preference
    overrides: ScenarioOverrides = Field(default_factory=ScenarioOverrides)


class ScenarioItem(RecommendationItem):
    """A recommendation item with its position in the base (no overrides) run."""

    base_rank: Optional[int] = Field(
        None,
        description="Rank in the base run; null if the vehicle was not in the base top 5.",
    )
    rank_change: Optional[int] = Field(
        None,
        description="base_rank - rank. Positive = moved up, negative = moved down, "
        "null if base_rank is unknown.",
    )


class ScenarioResult(BaseModel):
    status: Literal["success"] = "success"
    total_matches: int
    recommendations: List[ScenarioItem]
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    weights_used: Dict[str, int] = Field(default_factory=dict)
    annual_km_used: int
    fuel_price_try_used: float
    electricity_price_try_used: float


# Response union for the endpoint (no matches -> same ConflictReport as /api/recommendations).
ScenarioResponse = ScenarioResult | ConflictReport
