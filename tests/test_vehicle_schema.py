"""Tests for the shared Vehicle schema (app/schemas/vehicle.py)."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.engine.filters import apply_hard_filters
from app.schemas import VEHICLE_CSV_COLUMNS, Preference, Vehicle, VehicleListResponse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture_rows() -> list[dict[str, str]]:
    with (FIXTURES_DIR / "sample_vehicles.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _valid_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": "1",
        "brand": "Toyota",
        "model": "Corolla",
        "variant": "1.8 Hybrid Dream",
        "year": "2024",
        "body_type": "sedan",
        "fuel_type": "hybrid",
        "transmission": "automatic",
        "consumption_l_100km": "4.5",
        "consumption_kwh_100km": "",
        "range_km": "",
        "power_hp": "140",
        "seats": "5",
        "trunk_l": "471",
        "euro_ncap_stars": "5",
        "price_try": "1820000",
        "price_checked_at": "2026-11-16",
        "spec_source_url": "https://www.toyota.com.tr/modeller/corolla",
        "price_source_url": "https://www.toyota.com.tr/fiyat-listesi",
    }
    row.update(overrides)
    return row


# --- Contract with the CSV --------------------------------------------------


def test_csv_columns_match_schema_fields() -> None:
    assert tuple(Vehicle.model_fields) == VEHICLE_CSV_COLUMNS


def test_fixture_csv_header_matches_schema() -> None:
    with (FIXTURES_DIR / "sample_vehicles.csv").open(encoding="utf-8", newline="") as file:
        header = next(csv.reader(file))

    assert tuple(header) == VEHICLE_CSV_COLUMNS


def test_every_fixture_row_is_a_valid_vehicle() -> None:
    vehicles = [Vehicle.model_validate(row) for row in _fixture_rows()]

    assert len(vehicles) >= 10
    assert len({v.id for v in vehicles}) == len(vehicles)


# --- Parsing ----------------------------------------------------------------


def test_csv_strings_are_parsed_to_typed_values() -> None:
    vehicle = Vehicle.model_validate(_valid_row())

    assert vehicle.id == 1
    assert vehicle.consumption_l_100km == 4.5
    assert vehicle.price_try == 1_820_000
    assert vehicle.price_checked_at == dt.date(2026, 11, 16)


def test_empty_cells_become_none() -> None:
    vehicle = Vehicle.model_validate(_valid_row(power_hp="", trunk_l=" ", euro_ncap_stars=""))

    assert vehicle.power_hp is None
    assert vehicle.trunk_l is None
    assert vehicle.euro_ncap_stars is None


def test_enum_fields_are_plain_strings() -> None:
    vehicle = Vehicle.model_validate(_valid_row())

    assert type(vehicle.fuel_type) is str
    assert type(vehicle.body_type) is str
    assert vehicle.model_dump(mode="json")["fuel_type"] == "hybrid"


def test_vehicle_can_be_built_from_object_attributes() -> None:
    class Row:  # stands in for a SQLAlchemy model instance (T04)
        pass

    row = Row()
    for key, value in _valid_row().items():
        setattr(row, key, value)

    assert Vehicle.model_validate(row).brand == "Toyota"


# --- Validation errors ------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fuel_type", "lpg"),
        ("body_type", "coupe"),
        ("transmission", "cvt"),
        ("seats", "1"),
        ("euro_ncap_stars", "6"),
        ("price_try", "0"),
        ("price_try", "1.820.000"),
        ("price_checked_at", "16.11.2026"),
        ("spec_source_url", "toyota.com.tr"),
        ("brand", ""),
    ],
)
def test_invalid_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Vehicle.model_validate(_valid_row(**{field: value}))


@pytest.mark.parametrize("field", ["seats", "price_try", "price_checked_at", "spec_source_url"])
def test_required_fields_cannot_be_missing(field: str) -> None:
    row = _valid_row()
    del row[field]

    with pytest.raises(ValidationError):
        Vehicle.model_validate(row)


def test_unknown_column_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Vehicle.model_validate(_valid_row(colour="red"))


def test_electric_vehicle_cannot_have_fuel_consumption() -> None:
    row = _valid_row(fuel_type="electric", consumption_l_100km="5.0")

    with pytest.raises(ValidationError, match="consumption_l_100km"):
        Vehicle.model_validate(row)


@pytest.mark.parametrize("field", ["consumption_kwh_100km", "range_km"])
def test_combustion_vehicle_cannot_have_electric_values(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        Vehicle.model_validate(_valid_row(**{field: "400"}))


def test_electric_vehicle_with_electric_values_is_valid() -> None:
    row = _valid_row(
        fuel_type="electric",
        consumption_l_100km="",
        consumption_kwh_100km="15.7",
        range_km="455",
    )

    vehicle = Vehicle.model_validate(row)

    assert vehicle.consumption_l_100km is None
    assert vehicle.range_km == 455


# --- Integration with other modules ----------------------------------------


def test_vehicles_work_with_m3_hard_filters() -> None:
    vehicles = [Vehicle.model_validate(row) for row in _fixture_rows()]
    preference = Preference(budget_max_try=2_000_000, fuel_types=["electric"])

    matched = apply_hard_filters(vehicles, preference.hard_filter_criteria())

    assert matched
    assert all(v.fuel_type == "electric" and v.price_try <= 2_000_000 for v in matched)


def test_vehicle_list_response_shape() -> None:
    response = VehicleListResponse(total=1, items=[Vehicle.model_validate(_valid_row())])

    body = response.model_dump(mode="json")

    assert body["total"] == 1
    assert body["items"][0]["price_checked_at"] == "2026-11-16"
