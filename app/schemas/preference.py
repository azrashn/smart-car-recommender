"""Preference schema for M2 (Preference Input) — shared contract across all modules.

This schema is consumed by:
- T11/T12  : step-by-step survey form
- T13/T31  : rule-based and AI-based text extraction
- M3       : hard-constraint filtering and weighted scoring
- M6       : Scenario Lab (annual_km / fuel_price / priority overrides)

Design rules
------------
- Pydantic v2, extra="forbid" — unknown fields are rejected.
- No personal data fields (name, e-mail, location, etc.).
- Empty list for multi-value filter fields means "no preference" (all pass).
- Enum values are IDENTICAL to those used in data/vehicles.csv and app/engine/filters.py.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Enums — values must stay in sync with sample_vehicles.csv / filters.py
# ---------------------------------------------------------------------------


class FuelType(str, Enum):
    """Accepted fuel types — mirrors CSV column ``fuel_type``."""

    petrol = "petrol"
    diesel = "diesel"
    hybrid = "hybrid"
    electric = "electric"


class BodyType(str, Enum):
    """Accepted body types — mirrors CSV column ``body_type``."""

    hatchback = "hatchback"
    sedan = "sedan"
    suv = "suv"
    wagon = "wagon"
    mpv = "mpv"


class UsageType(str, Enum):
    """Primary driving context chosen by the user."""

    city = "city"
    highway = "highway"
    mixed = "mixed"
    family = "family"


class Priority(str, Enum):
    """Importance level for a scoring criterion.

    Maps to weights used by M3: low → 1, medium → 2, high → 3.
    """

    low = "low"
    medium = "medium"
    high = "high"


def priority_weight(p: Priority) -> int:
    """Return the numeric weight (1/2/3) for a Priority level.

    Scoring logic lives in M3; this helper only converts the enum value.

    >>> priority_weight(Priority.low)
    1
    >>> priority_weight(Priority.high)
    3
    """
    _map = {Priority.low: 1, Priority.medium: 2, Priority.high: 3}
    return _map[p]


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ScoringPriorities(BaseModel):
    """Per-criterion importance weights chosen by the user.

    Each field defaults to ``medium`` so a partially filled form is valid.
    Scoring logic (how weights are applied) belongs to M3, not here.
    """

    model_config = {"extra": "forbid"}

    fuel_economy: Priority = Field(
        default=Priority.medium,
        description="Importance of fuel / energy efficiency.",
    )
    interior_space: Priority = Field(
        default=Priority.medium,
        description="Importance of luggage capacity and seating comfort.",
    )
    performance: Priority = Field(
        default=Priority.medium,
        description="Importance of engine power and acceleration.",
    )
    budget_fit: Priority = Field(
        default=Priority.medium,
        description="Importance of staying well within the stated budget.",
    )
    safety: Priority = Field(
        default=Priority.medium,
        description="Importance of Euro NCAP safety rating.",
    )

    def weights(self) -> dict[str, int]:
        """Return a ``{criterion: weight}`` dict ready for M3 scorer.

        Example::

            prefs.priorities.weights()
            # {"fuel_economy": 3, "interior_space": 2, ...}
        """
        return {
            "fuel_economy": priority_weight(self.fuel_economy),
            "interior_space": priority_weight(self.interior_space),
            "performance": priority_weight(self.performance),
            "budget_fit": priority_weight(self.budget_fit),
            "safety": priority_weight(self.safety),
        }


# ---------------------------------------------------------------------------
# Main schema
# ---------------------------------------------------------------------------

_PositiveInt = Annotated[int, Field(gt=0)]
_NonNegativeInt = Annotated[int, Field(ge=0)]
_AnnualKm = Annotated[int, Field(ge=1_000, le=200_000)]
_MinSeats = Annotated[int, Field(ge=2, le=9)]


class Preference(BaseModel):
    """User preference input — the central contract for all AutoMatch modules.

    Hard-constraint fields (used as filters by M3)
    -----------------------------------------------
    ``budget_max_try``, ``transmission``, ``fuel_types``, ``body_types``,
    ``min_seats``

    Scoring fields (used as weighted criteria by M3)
    -------------------------------------------------
    ``priorities``  →  ``ScoringPriorities.weights()``

    Scenario Lab fields (overridden per scenario by M6)
    ----------------------------------------------------
    ``annual_km``

    Text-extraction fields (populated by T13 / T31)
    ------------------------------------------------
    All fields; partial fill is valid (missing fields reported separately).
    """

    model_config = {"extra": "forbid"}

    # --- Budget ---
    budget_max_try: _PositiveInt = Field(
        ...,
        description="Maximum purchase price in Turkish Lira (TRY). Required.",
    )
    budget_min_try: _NonNegativeInt | None = Field(
        default=None,
        description=(
            "Minimum purchase price in TRY (optional, >= 0). "
            "If set, must be less than or equal to budget_max_try."
        ),
    )

    # --- Usage ---
    usage_type: UsageType | None = Field(
        default=None,
        description=(
            "Primary driving context: city, highway, mixed, or family. "
            "Informs scoring but is not a hard filter."
        ),
    )
    annual_km: _AnnualKm | None = Field(
        default=None,
        description=(
            "Expected annual mileage in kilometres (1 000–200 000). "
            "Used by M5 for fuel cost estimates and by M6 for scenario recalculation."
        ),
    )

    # --- Hard-constraint filters ---
    transmission: Literal["manual", "automatic"] | None = Field(
        default=None,
        description=(
            "Required transmission type. None means no preference (all pass). "
            "Mirrors filter_by_transmission in app/engine/filters.py."
        ),
    )
    fuel_types: list[FuelType] = Field(
        default_factory=list,
        description=(
            "Accepted fuel types. Empty list means no preference (all pass). "
            "Values must match CSV column fuel_type."
        ),
    )
    body_types: list[BodyType] = Field(
        default_factory=list,
        description=(
            "Accepted body types. Empty list means no preference (all pass). "
            "Values must match CSV column body_type."
        ),
    )
    min_seats: _MinSeats | None = Field(
        default=None,
        description="Minimum required seat count (2–9). None means no preference.",
    )

    # --- Scoring weights ---
    priorities: ScoringPriorities = Field(
        default_factory=ScoringPriorities,
        description=(
            "Per-criterion importance levels (low / medium / high). "
            "Defaults to medium for all criteria. "
            "Call priorities.weights() to get the {criterion: 1|2|3} dict for M3."
        ),
    )

    # --- Localisation ---
    language: Literal["tr", "en"] = Field(
        default="tr",
        description="Preferred language for generated explanations (tr or en).",
    )

    # --- Cross-field validators ---
    @model_validator(mode="after")
    def _budget_min_lte_max(self) -> Preference:
        """Ensure budget_min_try does not exceed budget_max_try."""
        if (
            self.budget_min_try is not None
            and self.budget_max_try is not None
            and self.budget_min_try > self.budget_max_try
        ):
            raise ValueError(
                f"budget_min_try ({self.budget_min_try}) must be "
                f"<= budget_max_try ({self.budget_max_try})"
            )
        return self

    # --- Convenience helpers ---
    def hard_filter_criteria(self) -> dict:
        """Return a dict ready to pass directly to ``apply_hard_filters`` in M3.

        Example::

            from app.engine.filters import apply_hard_filters
            results = apply_hard_filters(vehicles, pref.hard_filter_criteria())
        """
        return {
            "budget_max": self.budget_max_try,
            "transmission": self.transmission,
            "fuel_types": [ft.value for ft in self.fuel_types],
            "seats_min": self.min_seats,
            "body_types": [bt.value for bt in self.body_types],
        }


# ---------------------------------------------------------------------------
# Preference Draft model (for partial text extraction)
# ---------------------------------------------------------------------------


class PreferenceDraft(Preference):
    """User preference draft where all fields, including budget_max_try, are optional.

    Used by text extraction (T13 / T31) to capture partial preferences from free text
    (e.g. user specifies "automatic SUV" without mentioning a budget).
    When the missing mandatory fields are provided by the user, call ``to_preference()``
    to obtain a full ``Preference`` object suitable for the recommendation engine (M3).
    """

    budget_max_try: _PositiveInt | None = Field(
        default=None,
        description="Maximum purchase price in TRY (optional in draft).",
    )

    def missing_required_fields(self) -> list[str]:
        """Return the names of mandatory fields missing to form a full Preference."""
        missing: list[str] = []
        if self.budget_max_try is None:
            missing.append("budget_max_try")
        return missing

    def to_preference(self) -> Preference:
        """Convert this draft to a fully-validated Preference object.

        Raises:
            ValueError: If any mandatory field (e.g. budget_max_try) is missing.
        """
        missing = self.missing_required_fields()
        if missing:
            fields_str = ", ".join(missing)
            raise ValueError(
                f"Cannot convert PreferenceDraft to Preference: missing required field(s): {fields_str}"
            )
        return Preference.model_validate(self.model_dump())


# ---------------------------------------------------------------------------
# Text-extraction result model (POST /api/preferences/text response)
# ---------------------------------------------------------------------------

_ExtractionMethod = Literal["ai", "rule"]

# Fields of Preference that may be absent after text extraction
_PREFERENCE_FIELDS = frozenset(Preference.model_fields.keys())


class TextExtractionResult(BaseModel):
    """Response schema for POST /api/preferences/text.

    Wraps a (possibly partial) ``PreferenceDraft`` with metadata about which fields
    could not be inferred and which extraction method was used.
    """

    model_config = {"extra": "forbid"}

    preference: PreferenceDraft = Field(
        ...,
        description="Extracted preference draft (may omit mandatory fields such as budget_max_try).",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Names of Preference fields that could not be inferred from the input text. "
            "The frontend should prompt the user to supply these."
        ),
    )
    method: _ExtractionMethod = Field(
        ...,
        description=(
            "Extraction method used: 'ai' (Gemini / LLM) or 'rule' (regex / keyword fallback)."
        ),
    )
