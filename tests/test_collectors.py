import json
import unittest

from matched_model.collectors import AiderCollector, ArtificialAnalysisCollector, DeepSWECollector
from matched_model.models import RawObservation


class TestCollectors(unittest.TestCase):
    def test_artificial_analysis_json_parse(self) -> None:
        payload = json.dumps({
            "data": [
                {
                    "name": "GPT 6.1 Sol",
                    "evaluations": {"artificial_analysis_intelligence_index": 53.2},
                    "pricing": {"price_1m_blended_3_to_1": 0.65},
                }
            ]
        })
        obs = ArtificialAnalysisCollector().parse_live(payload)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].model, "GPT 6.1 Sol")
        self.assertAlmostEqual(obs[0].raw_score, 53.2)

    def test_deepswe_html_table_parse(self) -> None:
        html = "<table><tr><td>Claude Opus 5.5</td><td>71.2%</td></tr></table>"
        obs = DeepSWECollector().parse_live(html)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].model, "Claude Opus 5.5")
        self.assertAlmostEqual(obs[0].raw_score, 71.2)

    def test_aider_json_parse(self) -> None:
        payload = json.dumps([{"model": "Qwen 3.5 Coder", "pass_rate_2": 74.0, "total_cost": 0.28}])
        obs = AiderCollector().parse_live(payload)
        self.assertEqual(len(obs), 1)
        self.assertAlmostEqual(obs[0].cost_usd, 0.28)

    def test_offline_fallback_returns_cached(self) -> None:
        cached = [RawObservation(source="deepswe", model="m1", raw_score=60.0)]
        res = DeepSWECollector().collect(cached, offline=True)
        self.assertEqual(res.status, "cached")
        self.assertEqual(len(res.observations), 1)


if __name__ == "__main__":
    unittest.main()
