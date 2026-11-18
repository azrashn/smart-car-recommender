"""Shared Pydantic schemas across all AutoMatch modules."""

from app.schemas.preference import (
    BodyType,
    FuelType,
    Preference,
    PreferenceDraft,
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
from app.schemas.vehicle import VEHICLE_CSV_COLUMNS, Vehicle, VehicleListResponse

__all__ = [
    "VEHICLE_CSV_COLUMNS",
    "BodyType",
    "ConflictReport",
    "FuelType",
    "Preference",
    "PreferenceDraft",
    "Priority",
    "RecommendationItem",
    "RecommendationResult",
    "RelaxationSuggestion",
    "ScoreBreakdown",
    "ScoringPriorities",
    "TextExtractionResult",
    "UsageType",
    "Vehicle",
    "VehicleListResponse",
    "priority_weight",
]
