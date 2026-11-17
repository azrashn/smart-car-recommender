"""Tests for T02: data/vehicles.csv follows docs/data-dictionary.md.

These checks run on every data PR, so a malformed row fails CI with its row number.
They only use the standard library; full type validation lives in app/schemas/vehicle.py.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
VEHICLES_CSV = ROOT_DIR / "data" / "vehicles.csv"
FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_vehicles.csv"

EXPECTED_COLUMNS = [
    "id",
    "brand",
    "model",
    "variant",
    "year",
    "body_type",
    "fuel_type",
    "transmission",
    "consumption_l_100km",
    "consumption_kwh_100km",
    "range_km",
    "power_hp",
    "seats",
    "trunk_l",
    "euro_ncap_stars",
    "price_try",
    "price_checked_at",
    "spec_source_url",
    "price_source_url",
]
REQUIRED_COLUMNS = [
    "id",
    "brand",
    "model",
    "variant",
    "year",
    "body_type",
    "fuel_type",
    "transmission",
    "seats",
    "price_try",
    "price_checked_at",
    "spec_source_url",
    "price_source_url",
]
ALLOWED_VALUES = {
    "body_type": {"hatchback", "sedan", "suv", "wagon", "mpv"},
    "fuel_type": {"petrol", "diesel", "hybrid", "electric"},
    "transmission": {"manual", "automatic"},
}


def _read_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as file:
        return next(csv.reader(file))


def _read_rows() -> list[tuple[int, dict[str, str]]]:
    """Return (line number in the file, row) pairs; line 1 is the header."""
    with VEHICLES_CSV.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, restkey="_extra")
        return [(index + 2, row) for index, row in enumerate(reader)]


def test_vehicles_csv_exists() -> None:
    assert VEHICLES_CSV.is_file(), "data/vehicles.csv is missing"


def test_header_matches_data_dictionary() -> None:
    assert _read_header(VEHICLES_CSV) == EXPECTED_COLUMNS


def test_header_matches_test_fixture() -> None:
    assert _read_header(VEHICLES_CSV) == _read_header(FIXTURE_CSV)


def test_csv_has_at_least_one_row() -> None:
    assert _read_rows(), "data/vehicles.csv has a header but no vehicles"


def test_file_is_utf8_without_bom() -> None:
    assert not VEHICLES_CSV.read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize(("line", "row"), _read_rows())
def test_row_follows_data_dictionary(line: int, row: dict[str, str]) -> None:
    errors: list[str] = []

    if "_extra" in row or None in row.values():
        errors.append(f"expected {len(EXPECTED_COLUMNS)} columns")
    else:
        for column in REQUIRED_COLUMNS:
            if not row[column].strip():
                errors.append(f"{column} is required")

        for column, allowed in ALLOWED_VALUES.items():
            if row[column] and row[column] not in allowed:
                errors.append(f"{column}={row[column]!r} not in {sorted(allowed)}")

        for column in ("id", "year", "seats", "price_try"):
            if row[column] and not row[column].isdigit():
                errors.append(f"{column}={row[column]!r} must be a whole number")

        try:
            dt.date.fromisoformat(row["price_checked_at"])
        except ValueError:
            errors.append("price_checked_at must be YYYY-MM-DD")

        for column in ("spec_source_url", "price_source_url"):
            if row[column] and not row[column].startswith(("http://", "https://")):
                errors.append(f"{column} must start with http:// or https://")

        if row["fuel_type"] == "electric":
            if row["consumption_l_100km"]:
                errors.append("electric vehicles must leave consumption_l_100km empty")
        else:
            for column in ("consumption_kwh_100km", "range_km"):
                if row[column]:
                    errors.append(f"{column} is only allowed for electric vehicles")

    assert not errors, f"data/vehicles.csv line {line}: " + "; ".join(errors)


def test_ids_are_unique_and_ascending() -> None:
    ids = [int(row["id"]) for _, row in _read_rows()]

    assert len(ids) == len(set(ids)), "duplicate id in data/vehicles.csv"
    assert ids == sorted(ids), "rows must be sorted by id"
    assert ids[0] >= 1
