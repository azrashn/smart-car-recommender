"""Unit tests for M3 Hard Constraint Filters (T21)."""

import csv
from pathlib import Path
import unittest

from app.engine.filters import (
    apply_hard_filters,
    evaluate_hard_filters,
    filter_by_body_type,
    filter_by_budget,
    filter_by_fuel_type,
    filter_by_seats,
    filter_by_transmission,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_sample_vehicles():
    """Helper to load vehicles from sample_vehicles.csv."""
    csv_file = FIXTURES_DIR / "sample_vehicles.csv"
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        vehicles = []
        for row in reader:
            # Cast numeric types for realistic testing
            row["id"] = int(row["id"])
            row["year"] = int(row["year"])
            row["price_try"] = int(row["price_try"])
            row["seats"] = int(row["seats"])
            row["power_hp"] = int(row["power_hp"])
            vehicles.append(row)
        return vehicles


class TestHardConstraintFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vehicles = load_sample_vehicles()
        assert len(cls.vehicles) == 10, "Should have 10 sample vehicles"

    def test_filter_by_budget(self):
        # Budget <= 1.000.000 TL: Egea (960k), i20 (920k)
        under_1m = filter_by_budget(self.vehicles, 1000000)
        self.assertEqual(len(under_1m), 2)
        models = {v["model"] for v in under_1m}
        self.assertEqual(models, {"Egea", "i20"})

        # Budget None or <= 0 should return all vehicles
        self.assertEqual(len(filter_by_budget(self.vehicles, None)), 10)
        self.assertEqual(len(filter_by_budget(self.vehicles, 0)), 10)

    def test_filter_by_transmission(self):
        automatics = filter_by_transmission(self.vehicles, "automatic")
        manuals = filter_by_transmission(self.vehicles, "manual")

        self.assertEqual(len(automatics), 6)
        self.assertEqual(len(manuals), 4)
        self.assertEqual(len(automatics) + len(manuals), 10)

        # Case-insensitivity test
        self.assertEqual(len(filter_by_transmission(self.vehicles, "AUTOMATIC")), 6)

        # "any" or None should return all
        self.assertEqual(len(filter_by_transmission(self.vehicles, "any")), 10)
        self.assertEqual(len(filter_by_transmission(self.vehicles, None)), 10)

    def test_filter_by_fuel_type(self):
        # Single fuel type: electric
        evs = filter_by_fuel_type(self.vehicles, "electric")
        self.assertEqual(len(evs), 2)
        self.assertEqual({v["model"] for v in evs}, {"Model Y", "Atto 3"})

        # Multiple fuel types: petrol and hybrid
        petrol_hybrid = filter_by_fuel_type(self.vehicles, ["petrol", "hybrid"])
        self.assertEqual(len(petrol_hybrid), 8)

        # Empty or any
        self.assertEqual(len(filter_by_fuel_type(self.vehicles, None)), 10)
        self.assertEqual(len(filter_by_fuel_type(self.vehicles, "any")), 10)

    def test_filter_by_seats(self):
        # All 10 cars in fixture have 5 seats
        min_5 = filter_by_seats(self.vehicles, 5)
        self.assertEqual(len(min_5), 10)

        # No 7-seater cars in fixture
        min_7 = filter_by_seats(self.vehicles, 7)
        self.assertEqual(len(min_7), 0)

        # None or 0 returns all
        self.assertEqual(len(filter_by_seats(self.vehicles, None)), 10)

    def test_filter_by_body_type(self):
        suvs = filter_by_body_type(self.vehicles, "suv")
        self.assertEqual(len(suvs), 4)
        self.assertEqual({v["model"] for v in suvs}, {"2008", "Model Y", "Atto 3", "Duster"})

        suv_sedan = filter_by_body_type(self.vehicles, ["suv", "sedan"])
        self.assertEqual(len(suv_sedan), 7)

    def test_apply_hard_filters_combined(self):
        # Criteria: Automatic SUV under 2.000.000 TL
        criteria = {
            "budget_max": 2000000,
            "transmission": "automatic",
            "body_types": ["suv"],
            "seats_min": 5,
        }
        filtered = apply_hard_filters(self.vehicles, criteria)
        # Matches: Peugeot 2008 (1.75M) and BYD Atto 3 (1.79M)
        # Model Y (2.2M) is excluded due to budget; Duster is manual
        self.assertEqual(len(filtered), 2)
        self.assertEqual({v["model"] for v in filtered}, {"2008", "Atto 3"})

    def test_evaluate_hard_filters_diagnostics(self):
        # Impossible criteria: Automatic under 1.000.000 TL
        criteria = {
            "budget_max": 1000000,
            "transmission": "automatic",
        }
        matched, eliminated = evaluate_hard_filters(self.vehicles, criteria)
        self.assertEqual(len(matched), 0)
        # Budget alone eliminates 8 cars (only 2 <= 1M)
        self.assertEqual(eliminated["budget_max"], 8)
        # Transmission alone eliminates 4 cars (4 are manual)
        self.assertEqual(eliminated["transmission"], 4)


if __name__ == "__main__":
    unittest.main()
