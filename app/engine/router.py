"""FastAPI Router for M3 (Recommendation Engine) — T25.

Endpoint:
POST /api/recommendations
Accepts: Preference JSON
Returns: RecommendationResult (Top 5 matches) or ConflictReport
"""

from __future__ import annotations

from typing import Any, Dict, Union

try:
    from fastapi import APIRouter, Body
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    APIRouter = object  # type: ignore

from app.engine.service import generate_recommendations
from app.schemas.recommendation import ConflictReport, RecommendationResult


if HAS_FASTAPI:
    router = APIRouter(prefix="/api", tags=["recommendations"])

    @router.post(
        "/recommendations",
        response_model=Union[RecommendationResult, ConflictReport],
        summary="Kullanıcı tercihlerine göre ilk 5 araç önerisini veya çelişki raporunu döner",
    )
    def post_recommendations(
        preference: Dict[str, Any] = Body(..., description="Kullanıcı tercihleri (Preference)"),
    ) -> Union[RecommendationResult, ConflictReport]:
        """Kullanıcının girdiği anket veya metin tercihlerini işler.
        
        Sert filtreleri geçen araçları puanlayarak ilk 5'i döner.
        Hiç araç bulunamazsa nedenlerini ve esnetme önerilerini içeren ConflictReport döner.
        """
        return generate_recommendations(preference)
else:
    router = None  # type: ignore
