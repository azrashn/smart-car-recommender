"""Recommendation and conflict report schemas for M3 (Recommendation Engine).

These schemas define the output contract of POST /api/recommendations and are
shared across M3, M4 (AI explanations), M5 (results UI & comparison), and M6 (Scenario Lab).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """Normalized sub-scores (0-100) for each evaluation criterion.

    Per NFR-04, criteria whose underlying vehicle data is missing are ``None``
    rather than guessed or displayed as ``0.0``.
    """

    fuel_economy: Optional[float] = Field(
        None, ge=0, le=100, description="Fuel/energy efficiency score (None if data missing)"
    )
    interior_space: Optional[float] = Field(
        None, ge=0, le=100, description="Luggage capacity and seating score (None if data missing)"
    )
    performance: Optional[float] = Field(
        None, ge=0, le=100, description="Engine power score (None if data missing)"
    )
    budget_fit: Optional[float] = Field(
        None, ge=0, le=100, description="Affordability within budget score (None if data missing)"
    )
    safety: Optional[float] = Field(
        None, ge=0, le=100, description="Euro NCAP safety rating score (None if not tested)"
    )


class RecommendationItem(BaseModel):
    """A single recommended vehicle item with detailed scoring and tags."""

    rank: int = Field(..., ge=1, le=5, description="Ranking position (1-5)")
    vehicle_id: int = Field(..., description="Unique vehicle ID from catalog")
    brand: str = Field(..., description="Vehicle brand (e.g. Toyota)")
    model: str = Field(..., description="Vehicle model (e.g. Corolla)")
    variant: str = Field(..., description="Variant name (e.g. 1.8 Hybrid Dream)")
    year: int = Field(..., description="Model year")
    price_try: int = Field(..., ge=0, description="Current price in TRY")
    body_type: str = Field(..., description="hatchback, sedan, suv, etc.")
    fuel_type: str = Field(..., description="petrol, diesel, hybrid, electric")
    transmission: str = Field(..., description="manual, automatic")
    score: float = Field(..., ge=0, le=100, description="Final weighted score (0-100)")
    score_breakdown: ScoreBreakdown = Field(..., description="Sub-scores per criterion")
    strengths: List[str] = Field(default_factory=list, description="Key strengths identified by engine")
    weaknesses: List[str] = Field(default_factory=list, description="Key drawbacks or compromises")
    explanation: Optional[str] = Field(
        None,
        description="Generated explanation text (AI or template fallback, from M4)",
    )
    estimated_annual_cost_try: Optional[float] = Field(
        None,
        description="Estimated annual fuel/energy cost in TRY (from M5)",
    )


class RecommendationResult(BaseModel):
    """Output schema for successful recommendations (up to top 5 vehicles)."""

    status: str = Field(default="success", description="Result status ('success')")
    total_matches: int = Field(..., ge=0, description="Total number of vehicles meeting hard constraints")
    recommendations: List[RecommendationItem] = Field(
        ...,
        max_length=5,
        description="Top ranked recommended vehicles (up to 5)",
    )
    applied_filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Hard constraints applied during filtering",
    )
    weights_used: Dict[str, int] = Field(
        default_factory=dict,
        description="Weight factors (1/2/3) used for scoring criteria",
    )


class RelaxationSuggestion(BaseModel):
    """Actionable advice on which constraint to relax to unlock more vehicle options."""

    constraint: str = Field(..., description="Field name of the constraint (e.g. 'budget_max')")
    current_value: Any = Field(..., description="Current constraint value that blocked matches")
    suggested_value: Any = Field(..., description="Proposed relaxed value")
    message: str = Field(..., description="User-friendly explanation of the relaxation impact")
    additional_matches_unlocked: int = Field(
        ...,
        ge=1,
        description="How many more vehicles become eligible with this relaxation",
    )


class ConflictReport(BaseModel):
    """Output schema when no vehicles meet the user's hard constraints."""

    status: str = Field(default="conflict", description="Result status ('conflict')")
    has_conflict: bool = Field(default=True, description="True if no vehicle matched")
    reason: str = Field(..., description="High-level reason why no vehicles were found")
    conflicting_constraints: List[str] = Field(
        ...,
        description="List of constraint names causing the empty result",
    )
    suggestions: List[RelaxationSuggestion] = Field(
        default_factory=list,
        description="Ranked list of constraint relaxations",
    )
    explanation: Optional[str] = Field(
        None,
        description="Natural language conflict explanation (AI or template fallback, from M4)",
    )
