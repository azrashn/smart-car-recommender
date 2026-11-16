"""Shared Pydantic schemas across all AutoMatch modules."""

from app.schemas.recommendation import (
    ConflictReport,
    RecommendationItem,
    RecommendationResult,
    RelaxationSuggestion,
    ScoreBreakdown,
)

__all__ = [
    "ConflictReport",
    "RecommendationItem",
    "RecommendationResult",
    "RelaxationSuggestion",
    "ScoreBreakdown",
]
