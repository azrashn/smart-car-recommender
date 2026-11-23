"""Unit tests for M3 Weighted Scoring Engine (T22)."""

import csv
from pathlib import Path
import unittest

from app.engine.scoring import (
    _get_equivalent_consumption,
    _normalize_higher_is_better,
    _normalize_lower_is_better,
    calculate_vehicle_total_score,
    compute_catalogue_bounds,
    score_and_rank_vehicles,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_sample_vehicles():
    """Helper to load vehicles from sample_vehicles.csv."""
    csv_file = FIXTURES_DIR / "sample_vehicles.csv"
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        vehicles = []
        for row in reader:
            row["id"] = int(row["id"])
            row["year"] = int(row["year"])
            row["price_try"] = int(row["price_try"])
            row["seats"] = int(row["seats"])
            row["power_hp"] = int(row["power_hp"])
            vehicles.append(row)
        return vehicles


class TestWeightedScoringEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vehicles = load_sample_vehicles()
        assert len(cls.vehicles) >= 10, "Should load at least 10 sample vehicles"

    def test_normalization_bounds(self):
        """Test min-max normalization functions."""
        # Lower is better (e.g. price, consumption)
        # min=4.0 (best -> 1.0), max=10.0 (worst -> 0.0)
        self.assertAlmostEqual(_normalize_lower_is_better(4.0, 4.0, 10.0), 1.0)
        self.assertAlmostEqual(_normalize_lower_is_better(10.0, 4.0, 10.0), 0.0)
        self.assertAlmostEqual(_normalize_lower_is_better(7.0, 4.0, 10.0), 0.5)

        # Higher is better (e.g. power, space)
        # min=100 (worst -> 0.0), max=200 (best -> 1.0)
        self.assertAlmostEqual(_normalize_higher_is_better(100.0, 100.0, 200.0), 0.0)
        self.assertAlmostEqual(_normalize_higher_is_better(200.0, 100.0, 200.0), 1.0)
        self.assertAlmostEqual(_normalize_higher_is_better(150.0, 100.0, 200.0), 0.5)

    def test_equivalent_consumption(self):
        """Verify electric cars get reasonable equivalent L/100km values."""
        tesla = next(v for v in self.vehicles if v["model"] == "Model Y")
        equiv = _get_equivalent_consumption(tesla)
        self.assertIsNotNone(equiv)
        # 15.7 kWh / 8.9 ≈ 1.76 L/100km
        self.assertLess(equiv, 2.5)

        corolla = next(v for v in self.vehicles if v["model"] == "Corolla")
        self.assertEqual(_get_equivalent_consumption(corolla), 4.5)

    def test_missing_data_exclusion_nfr04(self):
        """Verify missing criteria are excluded from both numerator and denominator."""
        # Vehicle with all 5 criteria present (e.g. 80 on each)
        complete_scores = {
            "fuel_economy": 80.0,
            "budget_fit": 80.0,
            "interior_space": 80.0,
            "performance": 80.0,
            "safety": 80.0,
        }
        weights = {"fuel_economy": 2, "budget_fit": 2, "interior_space": 2, "performance": 2, "safety": 2}
        total = calculate_vehicle_total_score(complete_scores, weights)
        self.assertEqual(total, 80.0)

        # Vehicle missing Euro NCAP safety (safety=None)
        missing_safety_scores = dict(complete_scores)
        missing_safety_scores["safety"] = None
        # Should still be 80.0 because safety weight is dropped from denominator!
        total_missing = calculate_vehicle_total_score(missing_safety_scores, weights)
        self.assertEqual(total_missing, 80.0)

    def test_weight_sensitivity(self):
        """Check that changing weights prioritizes vehicles accordingly."""
        bounds = compute_catalogue_bounds(self.vehicles)

        # Scenario 1: Focus heavily on fuel economy
        eco_weights = {"fuel_economy": 3, "performance": 1, "budget_fit": 1, "interior_space": 1, "safety": 1}
        eco_ranked = score_and_rank_vehicles(self.vehicles, weights=eco_weights, custom_bounds=bounds)
        top_eco_model = eco_ranked[0]["vehicle"]["model"]
        # Electric or hybrid should lead
        self.assertIn(top_eco_model, {"Model Y", "Atto 3", "Corolla"})

        # Scenario 2: Focus heavily on power / performance
        perf_weights = {"fuel_economy": 1, "performance": 3, "budget_fit": 1, "interior_space": 1, "safety": 1}
        perf_ranked = score_and_rank_vehicles(self.vehicles, weights=perf_weights, custom_bounds=bounds)
        top_perf_model = perf_ranked[0]["vehicle"]["model"]
        # Tesla Model Y has 299 HP (highest in fixture)
        self.assertEqual(top_perf_model, "Model Y")

    def test_score_and_rank_vehicles_output_structure(self):
        """Verify returned list has proper ranks, valid score ranges (0-100), and breakdown."""
        ranked = score_and_rank_vehicles(self.vehicles)
        self.assertEqual(len(ranked), len(self.vehicles))

        # Check descending order
        scores = [item["score"] for item in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

        for idx, item in enumerate(ranked, start=1):
            self.assertEqual(item["rank"], idx)
            self.assertGreaterEqual(item["score"], 0.0)
            self.assertLessEqual(item["score"], 100.0)
            breakdown = item["sub_scores"]
            self.assertIn("fuel_economy", breakdown)
            self.assertIn("budget_fit", breakdown)
            self.assertIn("interior_space", breakdown)
            self.assertIn("performance", breakdown)
            self.assertIn("safety", breakdown)

    def test_bounds_come_from_catalogue_not_filtered_list(self):
        """Scores must not depend on which vehicles survived the filters."""
        bounds = compute_catalogue_bounds(self.vehicles)
        corolla = next(v for v in self.vehicles if v["model"] == "Corolla")

        full = score_and_rank_vehicles(self.vehicles, custom_bounds=bounds)
        full_corolla = next(i for i in full if i["vehicle"]["model"] == "Corolla")

        # Only one vehicle left after filtering: with catalogue bounds its
        # sub-scores must stay the same (not all 100).
        single = score_and_rank_vehicles([corolla], custom_bounds=bounds)
        self.assertEqual(single[0]["sub_scores"], full_corolla["sub_scores"])
        self.assertEqual(single[0]["score"], full_corolla["score"])
        self.assertNotEqual(single[0]["sub_scores"]["performance"], 100.0)

        # Passing the catalogue directly gives the same result.
        via_catalogue = score_and_rank_vehicles([corolla], catalogue=self.vehicles)
        self.assertEqual(via_catalogue[0]["sub_scores"], full_corolla["sub_scores"])

    def test_unknown_trunk_excluded_from_space_bounds(self):
        """NFR-04: a vehicle with unknown trunk_l must not affect space bounds."""
        known = [
            {"trunk_l": 400, "seats": 5},
            {"trunk_l": 600, "seats": 5},
        ]
        unknown = {"trunk_l": "", "seats": 5}
        self.assertEqual(compute_catalogue_bounds(known)["space"], (650.0, 850.0))
        self.assertEqual(compute_catalogue_bounds(known + [unknown])["space"], (650.0, 850.0))
        none_trunk = {"trunk_l": None, "seats": 5}
        self.assertEqual(compute_catalogue_bounds(known + [none_trunk])["space"], (650.0, 850.0))

    def test_invalid_weights_rejected(self):
        """Weights outside 1–3 (0, negative, >3, non-int) raise ValueError."""
        scores = {"fuel_economy": 80.0, "safety": 60.0}
        for bad in (0, -1, 4, 2.5, True, "3"):
            with self.subTest(weight=bad):
                with self.assertRaises(ValueError):
                    calculate_vehicle_total_score(scores, {"fuel_economy": bad})
                with self.assertRaises(ValueError):
                    score_and_rank_vehicles(self.vehicles, weights={"fuel_economy": bad})
        for good in (1, 2, 3):
            calculate_vehicle_total_score(scores, {"fuel_economy": good})


if __name__ == "__main__":
    unittest.main()
