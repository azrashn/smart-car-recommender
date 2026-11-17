"""Shared Pydantic schemas across all AutoMatch modules."""

from app.schemas.preference import (
    BodyType,
    FuelType,
    Preference,
    Priority,
    ScoringPriorities,
    TextExtractionResult,
    UsageType,
    priority_weight,
)
from app.schemas.recommendation import (
    ConflictReport,
    RecommendationItem,
    RecommendationResult,
    RelaxationSuggestion,
    ScoreBreakdown,
)

__all__ = [
    # preference.py (M2)
    "BodyType",
    "FuelType",
    "Preference",
    "Priority",
    "ScoringPriorities",
    "TextExtractionResult",
    "UsageType",
    "priority_weight",
    # recommendation.py (M3)
    "ConflictReport",
    "RecommendationItem",
    "RecommendationResult",
    "RelaxationSuggestion",
    "ScoreBreakdown",
]
