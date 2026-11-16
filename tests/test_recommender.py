import unittest
from pathlib import Path

from matched_model.pipeline import run_pipeline
from matched_model.recommender import analyze_plan_markdown, recommend_model


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestRecommender(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = run_pipeline(repo_root=REPO_ROOT, offline=True)

    def test_trivial_task_picks_low_cost_model(self) -> None:
        rec = recommend_model(self.data["models"], phase="trivial", complexity="trivial")
        self.assertIsNotNone(rec.primary)
        self.assertLessEqual(rec.primary["cost"], 0.25)

    def test_overkill_warning_triggered_for_expensive_model_on_medium_task(self) -> None:
        rec = recommend_model(
            self.data["models"],
            phase="implement",
            complexity="medium",
            current_model_id="claude-opus-5.5",
        )
        self.assertTrue(any("OVERKILL WARNING" in d for d in rec.diagnostics))

    def test_underkill_warning_triggered_for_luna_on_high_task(self) -> None:
        rec = recommend_model(
            self.data["models"],
            phase="plan",
            complexity="high",
            current_model_id="gpt-6-luna",
        )
        self.assertTrue(any("UNDERKILL WARNING" in d for d in rec.diagnostics))

    def test_plan_markdown_analysis(self) -> None:
        sample_plan = """
        ## Architecture & Database Schema Design
        - Implement core REST API endpoint for user profiles
        - Fix failing integration tests and debug CI timeout
        - Update README documentation and formatting
        """
        rows = analyze_plan_markdown(sample_plan, self.data["models"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["phase"], "plan")
        self.assertEqual(rows[1]["phase"], "implement")
        self.assertEqual(rows[2]["phase"], "debug")
        self.assertEqual(rows[3]["phase"], "trivial")


if __name__ == "__main__":
    unittest.main()
