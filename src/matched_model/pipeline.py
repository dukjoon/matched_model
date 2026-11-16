"""End-to-end benchmark collection, domain re-ranking, and artifact generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from matched_model.collectors import ALL_COLLECTORS, CollectorResult
from matched_model.models import ModelRecord, RawObservation
from matched_model.scoring import build_model_records


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _compute_profile_rankings(
    records: list[ModelRecord], profiles: list[str]
) -> dict[str, list[dict[str, Any]]]:
    rankings: dict[str, list[dict[str, Any]]] = {}
    for prof in profiles:
        ranked = sorted(
            records,
            key=lambda r: r.profile_scores.get(prof, 0.0),
            reverse=True,
        )
        rankings[prof] = [
            {
                "rank": idx + 1,
                "id": r.id,
                "name": r.name,
                "score": round(r.profile_scores.get(prof, 0.0), 2),
                "coverageRatio": round(r.coverage_ratio, 3),
            }
            for idx, r in enumerate(ranked)
        ]
    return rankings


def _build_routing_rules(records: list[ModelRecord]) -> dict[str, Any]:
    """Precompute phase x complexity recommendations for agent Skill consumption."""
    from matched_model.recommender import COMPLEXITY_FLOORS, recommend_model

    rules: dict[str, Any] = {}
    phases = ["plan", "implement", "debug", "trivial"]
    complexities = list(COMPLEXITY_FLOORS.keys())

    for phase in phases:
        rules[phase] = {}
        for comp in complexities:
            rec = recommend_model(
                [r.to_dict() for r in records],
                phase=phase,
                complexity=comp,
            )
            rules[phase][comp] = {
                "min_score_required": rec.min_score_required,
                "primary": rec.primary,
                "alternative_budget": rec.alternative_budget,
                "alternative_high_assurance": rec.alternative_high_assurance,
            }
    return rules


def run_pipeline(
    repo_root: Path | None = None,
    offline: bool = False,
) -> dict[str, Any]:
    root = repo_root or default_repo_root()
    data_dir = root / "data"

    sources_cfg = _load_json(data_dir / "sources.json")
    aliases_cfg = _load_json(data_dir / "aliases.json")
    manual_cfg = _load_json(data_dir / "manual_overrides.json")
    cache_cfg = _load_json(data_dir / "snapshot_cache.json")

    cached_obs = [
        RawObservation(
            source=o["source"],
            model=o["model"],
            raw_score=float(o["raw_score"]),
            cost_usd=float(o["cost_usd"]) if o.get("cost_usd") is not None else None,
        )
        for o in cache_cfg.get("observations", [])
    ]

    all_observations: list[RawObservation] = []
    source_status: dict[str, Any] = {}

    for collector in ALL_COLLECTORS:
        res: CollectorResult = collector.collect(cached_obs, offline=offline)
        all_observations.extend(res.observations)
        source_status[res.source] = {
            "status": res.status,
            "count": len(res.observations),
            "message": res.message,
        }

    records = build_model_records(
        observations=all_observations,
        sources_cfg=sources_cfg,
        aliases_cfg=aliases_cfg,
        manual_overrides_cfg=manual_cfg,
    )

    profile_names = list(sources_cfg["task_profiles"].keys())
    rankings = _compute_profile_rankings(records, profile_names)

    payload = {
        "schemaVersion": "1.0.0",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "sourceStatus": source_status,
        "taskProfiles": sources_cfg["task_profiles"],
        "rankings": rankings,
        "models": [r.to_dict() for r in records],
    }

    _write_json(data_dir / "benchmarks.json", payload)
    _write_json(root / "docs" / "data" / "benchmarks.json", payload)

    routing_payload = {
        "lastUpdated": payload["lastUpdated"],
        "rules": _build_routing_rules(records),
    }
    _write_json(data_dir / "routing_rules.json", routing_payload)
    return payload
