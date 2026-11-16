import json
import unittest
from pathlib import Path

from matched_model.models import RawObservation
from matched_model.scoring import build_model_records, calibrate_source_scores


REPO_ROOT = Path(__file__).resolve().parents[1]


class TestScoring(unittest.TestCase):
    def setUp(self) -> None:
        self.sources_cfg = json.loads((REPO_ROOT / "data" / "sources.json").read_text("utf-8"))
        self.aliases_cfg = json.loads((REPO_ROOT / "data" / "aliases.json").read_text("utf-8"))
        self.manual_cfg = json.loads((REPO_ROOT / "data" / "manual_overrides.json").read_text("utf-8"))
        self.cache_cfg = json.loads((REPO_ROOT / "data" / "snapshot_cache.json").read_text("utf-8"))

    def test_cohort_calibration_normalizes_elo_and_percent(self) -> None:
        obs = [
            RawObservation(source="lmsys", model="m1", raw_score=1420),
            RawObservation(source="lmsys", model="m2", raw_score=1320),
            RawObservation(source="deepswe", model="m1", raw_score=70.0),
            RawObservation(source="deepswe", model="m2", raw_score=50.0),
        ]
        cal = calibrate_source_scores(obs)
        self.assertAlmostEqual(cal[("lmsys", "m1")], cal[("deepswe", "m1")], places=3)
        self.assertGreater(cal[("lmsys", "m1")], cal[("lmsys", "m2")])

    def test_consensus_promotion_requires_two_sources(self) -> None:
        obs = [
            RawObservation(source=o["source"], model=o["model"], raw_score=o["raw_score"], cost_usd=o.get("cost_usd"))
            for o in self.cache_cfg["observations"]
        ]
        obs.append(RawObservation(source="deepswe", model="OneSourceOnlyModel", raw_score=88.0))
        obs.append(RawObservation(source="deepswe", model="TwoSourceModel", raw_score=65.0))
        obs.append(RawObservation(source="livebench", model="TwoSourceModel", raw_score=72.0))

        records = build_model_records(obs, self.sources_cfg, self.aliases_cfg, self.manual_cfg)
        ids = {r.id for r in records}
        self.assertIn("qwen-3.5-coder", ids)
        self.assertIn("twosourcemodel", ids)
        self.assertNotIn("onesourceonlymodel", ids)

    def test_domain_reranking_differs_between_plan_and_implement(self) -> None:
        # Model A is strong in reasoning_planning (livebench), weak in code_generation (aider)
        # Model B is strong in code_generation (aider), weaker in reasoning_planning (livebench)
        obs = [
            RawObservation(source="livebench", model="model-a", raw_score=90.0),
            RawObservation(source="livebench", model="model-b", raw_score=60.0),
            RawObservation(source="aider", model="model-a", raw_score=55.0),
            RawObservation(source="aider", model="model-b", raw_score=88.0),
        ]
        records = build_model_records(obs, self.sources_cfg, {}, {"models": []})
        by_id = {r.id: r for r in records}
        self.assertGreater(by_id["model-a"].profile_scores["plan"], by_id["model-b"].profile_scores["plan"])
        self.assertGreater(by_id["model-b"].profile_scores["implement"], by_id["model-a"].profile_scores["implement"])


if __name__ == "__main__":
    unittest.main()
