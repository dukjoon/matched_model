"""Core data models for matched_model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawObservation:
    """Single benchmark observation from one source."""

    source: str
    model: str
    raw_score: float
    cost_usd: float | None = None
    latency_tps: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningStep:
    """Cost and intelligence/profile scores at a specific reasoning tier."""

    level: str  # "Low" | "Med" | "High" | "Max"
    cost: float
    score: float  # Composite score (0-100)
    profile_scores: dict[str, float] = field(default_factory=dict)
    is_pareto: bool = False


@dataclass
class ModelRecord:
    """Normalized, multi-benchmark model record."""

    id: str
    name: str
    provider: str
    harness: str
    is_codex: bool
    color: str
    sources: list[str]
    coverage_ratio: float
    dimension_scores: dict[str, float]
    profile_scores: dict[str, float]
    steps: list[ReasoningStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "harness": self.harness,
            "isCodex": self.is_codex,
            "color": self.color,
            "sources": self.sources,
            "coverageRatio": round(self.coverage_ratio, 3),
            "dimensionScores": {k: round(v, 2) for k, v in self.dimension_scores.items()},
            "profileScores": {k: round(v, 2) for k, v in self.profile_scores.items()},
            "steps": [
                {
                    "level": s.level,
                    "cost": round(s.cost, 4),
                    "score": round(s.score, 2),
                    "profileScores": {k: round(v, 2) for k, v in s.profile_scores.items()},
                    "isPareto": s.is_pareto,
                }
                for s in self.steps
            ],
        }


@dataclass
class Recommendation:
    """Right-sized model recommendation for a task."""

    phase: str
    complexity: str
    profile_used: str
    min_score_required: float
    max_cost_allowed: float | None
    primary: dict[str, Any] | None
    alternative_budget: dict[str, Any] | None
    alternative_high_assurance: dict[str, Any] | None
    diagnostics: list[str] = field(default_factory=list)
