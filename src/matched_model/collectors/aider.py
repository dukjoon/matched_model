"""Aider Polyglot Leaderboard collector."""

from __future__ import annotations

import json
import re

from matched_model.collectors.base import BaseCollector
from matched_model.models import RawObservation


class AiderCollector(BaseCollector):
    source_id = "aider"
    url = "https://aider.chat/docs/leaderboards/"

    def parse_live(self, raw_text: str) -> list[RawObservation]:
        observations: list[RawObservation] = []
        try:
            payload = json.loads(raw_text)
            if isinstance(payload, list):
                for row in payload:
                    name = row.get("model") or row.get("dirname")
                    score = row.get("pass_rate_2") or row.get("pass_rate_1") or row.get("score")
                    cost = row.get("total_cost")
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

        for match in re.finditer(
            r"<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>([\d.]+)%</td>",
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
