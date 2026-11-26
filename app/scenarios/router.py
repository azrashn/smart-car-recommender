"""POST /api/scenarios (T50, M6)."""

from __future__ import annotations

from fastapi import APIRouter

from app.scenarios.schemas import ScenarioRequest, ScenarioResponse
from app.scenarios.service import run_scenario

router = APIRouter(prefix="/api", tags=["scenarios"])


@router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    summary="Re-rank recommendations with annual km, fuel price and priority overrides",
)
def post_scenarios(request: ScenarioRequest) -> ScenarioResponse:
    """Run the base preference and the overridden scenario, and report rank changes."""
    return run_scenario(request)
