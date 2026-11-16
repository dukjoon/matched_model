"""DeepSWE (deepswe.datacurve.ai) benchmark collector."""

from __future__ import annotations

import json
import re

from matched_model.collectors.base import BaseCollector
from matched_model.models import RawObservation


class DeepSWECollector(BaseCollector):
    source_id = "deepswe"
    url = "https://deepswe.datacurve.ai/"

    def parse_live(self, raw_text: str) -> list[RawObservation]:
        observations: list[RawObservation] = []
        # Try JSON array or __NEXT_DATA__
        try:
            payload = json.loads(raw_text)
            if isinstance(payload, list):
                for row in payload:
                    name = row.get("model") or row.get("name")
                    score = row.get("score") or row.get("pass_rate") or row.get("resolved")
                    cost = row.get("cost") or row.get("avg_cost")
                    if name and isinstance(score, (int, float)):
                        observations.append(
                            RawObservation(
                                source=self.source_id,
                                model=str(name),
                                raw_score=float(score),
                                cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
                            )
                        )
                return observations
        except json.JSONDecodeError:
            pass

        next_data = self.parse_json_ld_or_next_data(raw_text)
        if isinstance(next_data, dict):
            props = next_data.get("props", {}).get("pageProps", {})
            rows = props.get("leaderboard") or props.get("models") or []
            if isinstance(rows, list):
                for row in rows:
                    name = row.get("model") or row.get("name")
                    score = row.get("score") or row.get("pass_rate")
                    cost = row.get("cost") or row.get("avg_cost")
                    if name and isinstance(score, (int, float)):
                        observations.append(
                            RawObservation(
                                source=self.source_id,
                                model=str(name),
                                raw_score=float(score),
                                cost_usd=float(cost) if isinstance(cost, (int, float)) else None,
                            )
                        )
                return observations

        # Fallback regex for simple HTML table rows
        for match in re.finditer(
            r"<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>([\d.]+)%?</td>",
            raw_text,
            re.DOTALL,
        ):
            name = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            try:
                score = float(match.group(2))
            except ValueError:
                continue
            if name:
                observations.append(
                    RawObservation(source=self.source_id, model=name, raw_score=score)
                )
        return observations
