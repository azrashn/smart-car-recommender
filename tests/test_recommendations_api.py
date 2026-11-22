"""Unit tests for POST /api/recommendations recommendation service (T25)."""

import unittest

from app.engine.service import generate_recommendations, load_catalog_vehicles
from app.schemas.recommendation import ConflictReport, RecommendationResult


class TestRecommendationsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vehicles = load_catalog_vehicles()
        assert len(cls.vehicles) >= 10, "Should load sample catalog vehicles"

    def test_recommendation_success_top_5(self):
        """Valid preference returns up to 5 ranked cars with score and breakdown."""
        preference = {
            "budget_max_try": 2000000,
            "transmission": "automatic",
            "seats_min": 5,
            "priorities": {
                "fuel_economy": "high",
                "budget_fit": "medium",
                "safety": "high",
            },
        }

        result = generate_recommendations(preference, vehicles=self.vehicles)

        self.assertIsInstance(result, RecommendationResult)
        self.assertEqual(result.status, "success")
        self.assertGreater(result.total_matches, 0)
        self.assertLessEqual(len(result.recommendations), 5)

        for rec in result.recommendations:
            self.assertGreaterEqual(rec.score, 0.0)
            self.assertLessEqual(rec.score, 100.0)
            self.assertIsNotNone(rec.score_breakdown)
            self.assertGreater(len(rec.strengths), 0)
            self.assertIsNotNone(rec.explanation)

    def test_recommendation_conflict_report_when_no_matches(self):
        """Unsatisfiable criteria returns a ConflictReport with relaxation suggestions."""
        # Electric SUV under 1.000.000 TL (Electric SUVs in fixture are 1.79M and 2.2M)
        preference = {
            "budget_max_try": 1000000,
            "fuel_types": ["electric"],
            "body_types": ["suv"],
        }

        result = generate_recommendations(preference, vehicles=self.vehicles)

        self.assertIsInstance(result, ConflictReport)
        self.assertEqual(result.status, "conflict")
        self.assertTrue(result.has_conflict)
        self.assertIn("budget_max", result.conflicting_constraints)
        self.assertGreater(len(result.suggestions), 0)

        # Check suggestions have actionable proposals
        first_suggestion = result.suggestions[0]
        self.assertTrue(first_suggestion.message)
        self.assertGreaterEqual(first_suggestion.additional_matches_unlocked, 1)

    def test_preference_model_compatibility(self):
        """Works seamlessly when passed as a dict or object."""
        class MockPreferenceObj:
            def model_dump(self):
                return {
                    "budget_max": 2500000,
                    "transmission": "any",
                }

        result = generate_recommendations(MockPreferenceObj(), vehicles=self.vehicles)
        self.assertIsInstance(result, RecommendationResult)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.recommendations), 5)


if __name__ == "__main__":
    unittest.main()
