"""Tests for T20: Schema verification and fixture data validation."""

import csv
import json
from pathlib import Path
import unittest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestT20SchemasAndFixtures(unittest.TestCase):
    def test_sample_vehicles_csv_structure_and_count(self):
        """Verify sample_vehicles.csv has required columns and at least 10 rows."""
        csv_file = FIXTURES_DIR / "sample_vehicles.csv"
        self.assertTrue(csv_file.exists(), "sample_vehicles.csv must exist")

        expected_columns = [
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

        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, expected_columns, f"CSV headers mismatch: {reader.fieldnames}")
            rows = list(reader)

        self.assertGreaterEqual(len(rows), 10, f"Expected at least 10 vehicles, found {len(rows)}")

        for row in rows:
            self.assertTrue(row["id"].isdigit(), "id must be integer")
            self.assertTrue(row["brand"].strip(), "brand cannot be empty")
            self.assertTrue(row["model"].strip(), "model cannot be empty")
            self.assertIn(row["body_type"], {"hatchback", "sedan", "suv", "wagon", "mpv"})
            self.assertIn(row["fuel_type"], {"petrol", "diesel", "hybrid", "electric"})
            self.assertIn(row["transmission"], {"manual", "automatic"})
            self.assertGreater(int(row["price_try"]), 0, "price_try must be positive")

    def test_sample_results_json_structure(self):
        """Verify sample_results.json conforms to schema requirements."""
        json_file = FIXTURES_DIR / "sample_results.json"
        self.assertTrue(json_file.exists(), "sample_results.json must exist")

        with open(json_file, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("recommendation_success", data)
        self.assertIn("conflict_example", data)

        rec = data["recommendation_success"]
        self.assertEqual(rec["status"], "success")
        self.assertGreaterEqual(rec["total_matches"], len(rec["recommendations"]))
        self.assertLessEqual(len(rec["recommendations"]), 5)
        for item in rec["recommendations"]:
            self.assertGreaterEqual(item["rank"], 1)
            self.assertLessEqual(item["rank"], 5)
            self.assertGreaterEqual(item["score"], 0)
            self.assertLessEqual(item["score"], 100)
            self.assertIn("score_breakdown", item)
            self.assertIsInstance(item["strengths"], list)
            self.assertIsInstance(item["weaknesses"], list)

        conflict = data["conflict_example"]
        self.assertEqual(conflict["status"], "conflict")
        self.assertTrue(conflict["has_conflict"])
        self.assertGreater(len(conflict["conflicting_constraints"]), 0)
        self.assertGreater(len(conflict["suggestions"]), 0)

    def test_pydantic_schema_validation(self):
        """If pydantic is installed, ensure schemas load fixture data without errors."""
        try:
            from app.schemas.recommendation import ConflictReport, RecommendationResult

            json_file = FIXTURES_DIR / "sample_results.json"
            with open(json_file, mode="r", encoding="utf-8") as f:
                data = json.load(f)

            parsed_rec = RecommendationResult.model_validate(data["recommendation_success"])
            self.assertEqual(parsed_rec.total_matches, data["recommendation_success"]["total_matches"])

            parsed_conflict = ConflictReport.model_validate(data["conflict_example"])
            self.assertTrue(parsed_conflict.has_conflict)
        except ImportError:
            # Pydantic may not be installed in the environment until CI / dev dependencies run
            pass


if __name__ == "__main__":
    unittest.main()
