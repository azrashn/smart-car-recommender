"""FastAPI entry point: API routers, the health check and the static frontend.

Run locally from the project root::

    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000 (frontend) or http://127.0.0.1:8000/docs (API).
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.config import STATIC_DIR, get_settings
from app.preferences.router import router as preferences_router


class HealthResponse(BaseModel):
    """Response body of ``GET /health``."""

    status: Literal["ok"] = "ok"
    app: str
    version: str
    ai_provider: str


def create_app() -> FastAPI:
    """Build the FastAPI application. Tests call this to get a fresh instance."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Explainable, scenario-based car recommendation API.",
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        """Liveness check: returns 200 when the application is up."""
        return HealthResponse(
            app=settings.app_name,
            version=__version__,
            ai_provider=settings.ai_provider,
        )

    # --- API routers: each module adds one import above and one line here ---
    # application.include_router(catalog_router)       # M1  T05  /api/vehicles
    application.include_router(preferences_router)  # M2  T12  /api/preferences
    # application.include_router(engine_router)        # M3  T25  /api/recommendations
    # application.include_router(compare_router)       # M5  T42  /api/compare
    # application.include_router(scenarios_router)     # M6  T50  /api/scenarios

    # The static frontend is mounted LAST, because "/" matches every path and
    # would otherwise hide the API routes registered above.
    application.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return application


app = create_app()
