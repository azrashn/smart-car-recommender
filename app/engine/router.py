"""FastAPI Router for M3 (Recommendation Engine) — T25.

Endpoint:
POST /api/recommendations
Accepts: Preference JSON (validated by Pydantic; invalid input returns 422)
Returns: RecommendationResult (Top 5 matches) or ConflictReport
"""

from __future__ import annotations

from typing import Union

from fastapi import APIRouter

from app.engine.service import generate_recommendations
from app.schemas.preference import Preference
from app.schemas.recommendation import ConflictReport, RecommendationResult

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.post(
    "/recommendations",
    response_model=Union[RecommendationResult, ConflictReport],
    summary="Kullanıcı tercihlerine göre ilk 5 araç önerisini veya çelişki raporunu döner",
)
def post_recommendations(
    preference: Preference,
) -> Union[RecommendationResult, ConflictReport]:
    """Kullanıcının girdiği anket veya metin tercihlerini işler.

    Sert filtreleri geçen araçları tam katalog sınırlarına göre puanlayarak ilk 5'i döner.
    Hiç araç bulunamazsa nedenlerini ve esnetme önerilerini içeren ConflictReport döner.
    """
    return generate_recommendations(preference)
