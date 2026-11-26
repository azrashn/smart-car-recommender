"""Safe normalisation of a validated survey-form ``Preference``.

Validation (ranges, enums, budget ordering) is done by Pydantic in
``app/schemas/preference.py``. This module only cleans up values that are
valid but redundant. It never invents, adds or removes fields.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from app.schemas.preference import Preference

_E = TypeVar("_E", bound=Enum)


def _dedupe(values: list[_E]) -> list[_E]:
    """Remove repeated items while keeping the first-seen order."""
    return list(dict.fromkeys(values))


def normalize_preference(pref: Preference) -> Preference:
    """Return a copy of ``pref`` with duplicate ``fuel_types``/``body_types`` removed."""
    return pref.model_copy(
        update={
            "fuel_types": _dedupe(pref.fuel_types),
            "body_types": _dedupe(pref.body_types),
        }
    )
