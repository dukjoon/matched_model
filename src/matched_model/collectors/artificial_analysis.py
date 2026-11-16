"""Artificial Analysis benchmark collector."""

from __future__ import annotations

import json
import os
import urllib.request

from matched_model.collectors.base import BaseCollector
from matched_model.models import RawObservation


class ArtificialAnalysisCollector(BaseCollector):
    source_id = "artificial_analysis"
    url = "https://artificialanalysis.ai/models"
    api_url = "https://artificialanalysis.ai/api/v2/data/llms/models"

    def fetch_text(self, url: str | None = None) -> str:
        api_key = os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")
        if api_key and url is None:
            req = urllib.request.Request(
                self.api_url,
                headers={
                    "x-api-key": api_key,
                    "User-Agent": "matched-model-bot/0.1",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                return resp.read().decode("utf-8", errors="replace")
        return super().fetch_text(url)

    def parse_live(self, raw_text: str) -> list[RawObservation]:
        observations: list[RawObservation] = []
        # 1. Try JSON API payload
        try:
            payload = json.loads(raw_text)
            rows = payload.get("data", payload) if isinstance(payload, dict) else payload
            if isinstance(rows, list):
                for row in rows:
                    name = row.get("name") or row.get("slug")
                    evals = row.get("evaluations") or {}
                    score = evals.get("artificial_analysis_intelligence_index") or row.get("intelligence_index")
                    pricing = row.get("pricing") or {}
                    cost = pricing.get("price_1m_blended_3_to_1")
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

        # 2. Try __NEXT_DATA__ embedded JSON
        next_data = self.parse_json_ld_or_next_data(raw_text)
        if isinstance(next_data, dict):
            props = next_data.get("props", {}).get("pageProps", {})
            models = props.get("models") or props.get("initialModels") or []
            if isinstance(models, list):
                for m in models:
                    name = m.get("name") or m.get("model_name")
                    score = m.get("intelligence_index") or m.get("quality_index")
                    if name and isinstance(score, (int, float)):
                        observations.append(
                            RawObservation(
                                source=self.source_id,
                                model=str(name),
                                raw_score=float(score),
                            )
                        )
        return observations
