"""Base collector interface and HTTP/HTML extraction helpers."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from matched_model.models import RawObservation


@dataclass
class CollectorResult:
    source: str
    status: str  # "live" | "cached" | "error"
    observations: list[RawObservation]
    message: str = ""


class BaseCollector(ABC):
    """Abstract benchmark collector with graceful offline/cached fallback."""

    source_id: str = ""
    url: str = ""
    timeout_sec: float = 8.0

    def fetch_text(self, url: str | None = None) -> str:
        target = url or self.url
        req = urllib.request.Request(
            target,
            headers={
                "User-Agent": "matched-model-bot/0.1 (+https://github.com/matched-model)"
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def parse_json_ld_or_next_data(self, html: str) -> Any | None:
        """Attempt to extract embedded __NEXT_DATA__ or JSON blocks from HTML."""
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        return None

    @abstractmethod
    def parse_live(self, raw_text: str) -> list[RawObservation]:
        """Parse live HTTP response into RawObservation items."""

    def collect(
        self,
        cached_observations: list[RawObservation],
        offline: bool = False,
    ) -> CollectorResult:
        source_cached = [o for o in cached_observations if o.source == self.source_id]
        if offline:
            return CollectorResult(
                source=self.source_id,
                status="cached",
                observations=source_cached,
                message="offline mode: using snapshot cache",
            )
        try:
            raw_text = self.fetch_text()
            parsed = self.parse_live(raw_text)
            if parsed:
                return CollectorResult(
                    source=self.source_id,
                    status="live",
                    observations=parsed,
                    message=f"fetched {len(parsed)} live observations",
                )
            return CollectorResult(
                source=self.source_id,
                status="cached",
                observations=source_cached,
                message="live page yielded 0 parseable rows (client-rendered or changed); using cache",
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            return CollectorResult(
                source=self.source_id,
                status="cached",
                observations=source_cached,
                message=f"live fetch unavailable ({type(exc).__name__}); using cache",
            )
