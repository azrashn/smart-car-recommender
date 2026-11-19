"""HTTP routes for M2 (Preference Input)."""

from __future__ import annotations

from fastapi import APIRouter

from app.preferences.form_parser import normalize_preference
from app.schemas.preference import Preference

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.post("/form", response_model=Preference)
def submit_form(preference: Preference) -> Preference:
    """Validate a completed survey form and return the normalised ``Preference``."""
    return normalize_preference(preference)
