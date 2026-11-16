"""Terminal-Bench collector."""

from __future__ import annotations

import json

from matched_model.collectors.base import BaseCollector
from matched_model.models import RawObservation


class TerminalBenchCollector(BaseCollector):
    source_id = "terminal_bench"
    url = "https://www.tbench.ai/"

    def parse_live(self, raw_text: str) -> list[RawObservation]:
        observations: list[RawObservation] = []
        try:
            payload = json.loads(raw_text)
            rows = payload.get("leaderboard", payload) if isinstance(payload, dict) else payload
            if isinstance(rows, list):
                for row in rows:
                    name = row.get("model") or row.get("name")
                    score = row.get("accuracy") or row.get("score")
                    if name and isinstance(score, (int, float)):
                        observations.append(
                            RawObservation(
                                source=self.source_id,
                                model=str(name),
                                raw_score=float(score),
                            )
                        )
        except json.JSONDecodeError:
            pass
        return observations
