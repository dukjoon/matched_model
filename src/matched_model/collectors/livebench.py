"""LiveBench collector."""

from __future__ import annotations

import json

from matched_model.collectors.base import BaseCollector
from matched_model.models import RawObservation


class LiveBenchCollector(BaseCollector):
    source_id = "livebench"
    url = "https://livebench.ai/"

    def parse_live(self, raw_text: str) -> list[RawObservation]:
        observations: list[RawObservation] = []
        try:
            payload = json.loads(raw_text)
            if isinstance(payload, list):
                for row in payload:
                    name = row.get("model") or row.get("name")
                    score = row.get("global_average") or row.get("score")
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
