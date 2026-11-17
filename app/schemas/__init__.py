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
    "BodyType",
    "ConflictReport",
    "FuelType",
    "Preference",
    "Priority",
    "RecommendationItem",
    "RecommendationResult",
    "RelaxationSuggestion",
    "ScoreBreakdown",
    "ScoringPriorities",
    "TextExtractionResult",
    "UsageType",
    "priority_weight",
]
