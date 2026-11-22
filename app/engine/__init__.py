"""AutoMatch M3 Engine package."""

from app.engine.filters import (
    apply_hard_filters,
    evaluate_hard_filters,
    filter_by_body_type,
    filter_by_budget,
    filter_by_fuel_type,
    filter_by_seats,
    filter_by_transmission,
)
from app.engine.router import router
from app.engine.scoring import (
    calculate_vehicle_sub_scores,
    calculate_vehicle_total_score,
    compute_catalogue_bounds,
    score_and_rank_vehicles,
)
from app.engine.service import generate_recommendations, load_catalog_vehicles

__all__ = [
    "apply_hard_filters",
    "calculate_vehicle_sub_scores",
    "calculate_vehicle_total_score",
    "compute_catalogue_bounds",
    "evaluate_hard_filters",
    "filter_by_body_type",
    "filter_by_budget",
    "filter_by_fuel_type",
    "filter_by_seats",
    "filter_by_transmission",
    "generate_recommendations",
    "load_catalog_vehicles",
    "router",
    "score_and_rank_vehicles",
]
