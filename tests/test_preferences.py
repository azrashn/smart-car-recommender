"""Tests for T10: Preference schema validation.

Covers:
- All sample fixtures parse without errors (happy path)
- Invalid budget (negative / zero)
- budget_min_try > budget_max_try
- Unknown extra field rejected (extra='forbid')
- Invalid enum values for fuel_type, body_type, transmission, usage_type, priority
- annual_km out of valid range
- priority_weight() helper correctness
- ScoringPriorities.weights() output shape
- Preference.hard_filter_criteria() output shape
- TextExtractionResult round-trip
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.preference import (
    BodyType,
    FuelType,
    Preference,
    Priority,
    ScoringPriorities,
    TextExtractionResult,
    UsageType,
    priority_weight,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PREFERENCES_FILE = FIXTURES_DIR / "sample_preferences.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_KEYS = {"_comment", "_description"}


def _load_fixture(key: str) -> dict:
    with open(PREFERENCES_FILE, encoding="utf-8") as fh:
        raw = json.load(fh)
    sample = dict(raw[key])
    # Strip commentary keys before passing to Pydantic
    for k in _SKIP_KEYS:
        sample.pop(k, None)
    return sample


# ---------------------------------------------------------------------------
# Happy-path: all fixture examples must validate
# ---------------------------------------------------------------------------


class TestFixtureRoundTrip:
    """All sample_preferences.json entries must parse and re-serialise cleanly."""

    @pytest.mark.parametrize(
        "key",
        ["city_economy", "family_suv", "electric_priority", "maximal_constraints"],
    )
    def test_fixture_valid(self, key: str) -> None:
        data = _load_fixture(key)
        pref = Preference.model_validate(data)
        assert pref.budget_max_try > 0

    def test_city_economy_fields(self) -> None:
        pref = Preference.model_validate(_load_fixture("city_economy"))
        assert pref.usage_type == UsageType.city
        assert pref.transmission == "manual"
        assert FuelType.petrol in pref.fuel_types
        assert pref.priorities.fuel_economy == Priority.high

    def test_family_suv_budget_range(self) -> None:
        pref = Preference.model_validate(_load_fixture("family_suv"))
        assert pref.budget_min_try is not None
        assert pref.budget_min_try <= pref.budget_max_try
        assert BodyType.suv in pref.body_types

    def test_electric_priority_no_transmission(self) -> None:
        pref = Preference.model_validate(_load_fixture("electric_priority"))
        assert pref.transmission is None
        assert FuelType.electric in pref.fuel_types
        assert pref.language == "en"

    def test_maximal_constraints_serialise(self) -> None:
        data = _load_fixture("maximal_constraints")
        pref = Preference.model_validate(data)
        dumped = pref.model_dump(mode="json")
        # Round-trip: re-parse the serialised form
        pref2 = Preference.model_validate(dumped)
        assert pref2 == pref


# ---------------------------------------------------------------------------
# Budget validation
# ---------------------------------------------------------------------------


class TestBudgetValidation:
    def test_negative_budget_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=-100000)

    def test_zero_budget_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=0)

    def test_budget_min_gt_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="budget_min_try"):
            Preference(budget_max_try=1_000_000, budget_min_try=1_500_000)

    def test_budget_min_equal_max_accepted(self) -> None:
        pref = Preference(budget_max_try=1_000_000, budget_min_try=1_000_000)
        assert pref.budget_min_try == pref.budget_max_try

    def test_budget_min_lt_max_accepted(self) -> None:
        pref = Preference(budget_max_try=2_000_000, budget_min_try=1_000_000)
        assert pref.budget_min_try < pref.budget_max_try

    def test_negative_budget_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, budget_min_try=-1)


# ---------------------------------------------------------------------------
# Extra fields rejected
# ---------------------------------------------------------------------------


class TestExtraFieldsForbidden:
    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(
            ValidationError, match="extra_forbidden|Extra inputs are not permitted"
        ):
            Preference(budget_max_try=1_000_000, owner_name="Fatih")

    def test_scoring_priorities_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ScoringPriorities(unknown_criterion="high")


# ---------------------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------------------


class TestEnumValidation:
    def test_invalid_fuel_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, fuel_types=["gasoline"])

    def test_invalid_body_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, body_types=["coupe"])

    def test_invalid_transmission_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, transmission="semi-automatic")

    def test_invalid_usage_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, usage_type="offroad")

    def test_invalid_priority_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(
                budget_max_try=1_000_000,
                priorities=ScoringPriorities(fuel_economy="very_high"),  # type: ignore[arg-type]
            )

    def test_invalid_language_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, language="de")


# ---------------------------------------------------------------------------
# annual_km range
# ---------------------------------------------------------------------------


class TestAnnualKmRange:
    def test_annual_km_too_low_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, annual_km=500)

    def test_annual_km_too_high_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Preference(budget_max_try=1_000_000, annual_km=250_000)

    def test_annual_km_lower_bound_accepted(self) -> None:
        pref = Preference(budget_max_try=1_000_000, annual_km=1_000)
        assert pref.annual_km == 1_000

    def test_annual_km_upper_bound_accepted(self) -> None:
        pref = Preference(budget_max_try=1_000_000, annual_km=200_000)
        assert pref.annual_km == 200_000

    def test_annual_km_none_accepted(self) -> None:
        pref = Preference(budget_max_try=1_000_000, annual_km=None)
        assert pref.annual_km is None


# ---------------------------------------------------------------------------
# priority_weight() helper
# ---------------------------------------------------------------------------


class TestPriorityWeight:
    def test_low_returns_1(self) -> None:
        assert priority_weight(Priority.low) == 1

    def test_medium_returns_2(self) -> None:
        assert priority_weight(Priority.medium) == 2

    def test_high_returns_3(self) -> None:
        assert priority_weight(Priority.high) == 3


# ---------------------------------------------------------------------------
# ScoringPriorities.weights()
# ---------------------------------------------------------------------------


class TestScoringPrioritiesWeights:
    def test_default_all_medium(self) -> None:
        sp = ScoringPriorities()
        w = sp.weights()
        assert set(w.keys()) == {
            "fuel_economy",
            "interior_space",
            "performance",
            "budget_fit",
            "safety",
        }
        assert all(v == 2 for v in w.values())

    def test_custom_weights(self) -> None:
        sp = ScoringPriorities(
            fuel_economy=Priority.high,
            budget_fit=Priority.high,
            performance=Priority.low,
        )
        w = sp.weights()
        assert w["fuel_economy"] == 3
        assert w["budget_fit"] == 3
        assert w["performance"] == 1
        assert w["interior_space"] == 2  # default medium


# ---------------------------------------------------------------------------
# Preference.hard_filter_criteria()
# ---------------------------------------------------------------------------


class TestHardFilterCriteria:
    def test_criteria_keys(self) -> None:
        pref = Preference(
            budget_max_try=1_500_000,
            transmission="automatic",
            fuel_types=[FuelType.petrol, FuelType.hybrid],
            body_types=[BodyType.suv],
            min_seats=5,
        )
        criteria = pref.hard_filter_criteria()
        assert criteria["budget_max"] == 1_500_000
        assert criteria["transmission"] == "automatic"
        assert set(criteria["fuel_types"]) == {"petrol", "hybrid"}
        assert criteria["body_types"] == ["suv"]
        assert criteria["seats_min"] == 5

    def test_empty_lists_pass_through(self) -> None:
        pref = Preference(budget_max_try=1_000_000)
        criteria = pref.hard_filter_criteria()
        assert criteria["fuel_types"] == []
        assert criteria["body_types"] == []
        assert criteria["transmission"] is None
        assert criteria["seats_min"] is None


# ---------------------------------------------------------------------------
# TextExtractionResult
# ---------------------------------------------------------------------------


class TestTextExtractionResult:
    def test_valid_ai_result(self) -> None:
        pref = Preference(budget_max_try=1_200_000, fuel_types=[FuelType.electric])
        result = TextExtractionResult(
            preference=pref,
            missing_fields=["annual_km", "usage_type"],
            method="ai",
        )
        assert result.method == "ai"
        assert "annual_km" in result.missing_fields

    def test_valid_rule_result(self) -> None:
        pref = Preference(budget_max_try=900_000, transmission="manual")
        result = TextExtractionResult(preference=pref, missing_fields=[], method="rule")
        assert result.method == "rule"
        assert result.missing_fields == []

    def test_invalid_method_rejected(self) -> None:
        pref = Preference(budget_max_try=1_000_000)
        with pytest.raises(ValidationError):
            TextExtractionResult(preference=pref, missing_fields=[], method="gpt")  # type: ignore[arg-type]

    def test_extra_field_rejected(self) -> None:
        pref = Preference(budget_max_try=1_000_000)
        with pytest.raises(ValidationError):
            TextExtractionResult(
                preference=pref,
                missing_fields=[],
                method="rule",
                confidence=0.9,  # unknown field
            )
