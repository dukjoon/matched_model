"""Domain-aware benchmark calibration, consensus discovery, and Pareto scoring."""

from __future__ import annotations

import math
import re
from statistics import mean, pstdev
from typing import Any

from matched_model.models import ModelRecord, RawObservation, ReasoningStep

DEFAULT_COLORS = [
    "#38bdf8",
    "#f59e0b",
    "#ec4899",
    "#84cc16",
    "#14b8a6",
    "#a855f7",
]


def _slugify(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9.]+", "-", name.lower()).strip("-")
    return cleaned or "unknown-model"


def build_alias_lookup(aliases_cfg: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical_id, variants in aliases_cfg.items():
        lookup[canonical_id.lower()] = canonical_id
        for v in variants:
            lookup[v.lower()] = canonical_id
    return lookup


def resolve_canonical_id(raw_name: str, alias_lookup: dict[str, str]) -> str:
    key = raw_name.strip().lower()
    if key in alias_lookup:
        return alias_lookup[key]
    slug = _slugify(raw_name)
    return alias_lookup.get(slug, slug)


def calibrate_source_scores(observations: list[RawObservation]) -> dict[tuple[str, str], float]:
    """Calibrate raw scores within each benchmark source onto a common ~[22, 66] scale.

    Uses robust z-score + tanh compression so heterogeneous metrics (Elo 1300+,
    SWE-bench %, AA Intelligence Index) can be combined without scale distortion.
    """
    by_source: dict[str, list[RawObservation]] = {}
    for obs in observations:
        by_source.setdefault(obs.source, []).append(obs)

    calibrated: dict[tuple[str, str], float] = {}
    for source, items in by_source.items():
        scores = [i.raw_score for i in items]
        mu = mean(scores)
        sigma = pstdev(scores) if len(scores) > 1 else 0.0
        for item in items:
            if sigma < 1e-6:
                scaled = 50.0
            else:
                z = (item.raw_score - mu) / sigma
                # Maps z in [-2, +2] smoothly into ~[26, 74] centered at 50
                scaled = 50.0 + 18.0 * math.tanh(z * 0.65)
            calibrated[(source, item.model)] = scaled
    return calibrated


def _infer_provider_and_harness(model_id: str) -> tuple[str, str]:
    lower = model_id.lower()
    if "gpt" in lower or "codex" in lower:
        return "openai", "codex-cli"
    if "claude" in lower or "opus" in lower or "sonnet" in lower:
        return "anthropic", "claude-code"
    if "gemini" in lower:
        return "google", "gemini-cli"
    if "deepseek" in lower:
        return "deepseek", "open-harness"
    if "qwen" in lower:
        return "alibaba", "open-harness"
    return "community", "api"


def _synthesize_steps(anchor_cost: float, anchor_score: float) -> list[dict[str, Any]]:
    """Synthesize Low/Med/High/Max reasoning curve for consensus-discovered models."""
    cost = max(0.05, anchor_cost)
    return [
        {"level": "Low", "cost": round(cost * 0.35, 3), "score": round(anchor_score - 4.5, 2)},
        {"level": "Med", "cost": round(cost, 3), "score": round(anchor_score, 2)},
        {"level": "High", "cost": round(cost * 1.9, 3), "score": round(anchor_score + 3.0, 2)},
        {"level": "Max", "cost": round(cost * 3.1, 3), "score": round(anchor_score + 5.0, 2)},
    ]


def compute_pareto_flags(records: list[ModelRecord], profile: str = "composite") -> None:
    """Mark (model, step) pairs that lie on the Pareto frontier for a given profile."""
    points: list[tuple[float, float, ReasoningStep]] = []
    for rec in records:
        for step in rec.steps:
            score = step.profile_scores.get(profile, step.score)
            points.append((step.cost, score, step))
            step.is_pareto = False

    # Sort by cost ascending, then score descending
    points.sort(key=lambda p: (p[0], -p[1]))
    best_score_so_far = float("-inf")
    for _cost, score, step in points:
        if score > best_score_so_far + 1e-9:
            step.is_pareto = True
            best_score_so_far = score


def build_model_records(
    observations: list[RawObservation],
    sources_cfg: dict[str, Any],
    aliases_cfg: dict[str, list[str]],
    manual_overrides_cfg: dict[str, Any],
) -> list[ModelRecord]:
    """Aggregate multi-benchmark observations into domain-re-ranked ModelRecords."""
    alias_lookup = build_alias_lookup(aliases_cfg)
    dimensions: list[str] = sources_cfg["dimensions"]
    sources_meta: dict[str, Any] = sources_cfg["sources"]
    task_profiles: dict[str, Any] = sources_cfg["task_profiles"]
    min_consensus = int(sources_cfg.get("consensus_min_sources", 2))

    # Resolve canonical IDs on observations
    canonical_obs: list[RawObservation] = []
    for obs in observations:
        cid = resolve_canonical_id(obs.model, alias_lookup)
        canonical_obs.append(
            RawObservation(
                source=obs.source,
                model=cid,
                raw_score=obs.raw_score,
                cost_usd=obs.cost_usd,
                latency_tps=obs.latency_tps,
                metadata=obs.metadata,
            )
        )

    calibrated = calibrate_source_scores(canonical_obs)

    # Group observations by canonical model ID
    obs_by_model: dict[str, list[RawObservation]] = {}
    for obs in canonical_obs:
        obs_by_model.setdefault(obs.model, []).append(obs)

    manual_by_id: dict[str, dict[str, Any]] = {
        m["id"]: m for m in manual_overrides_cfg.get("models", [])
    }

    # Active roster = manual overrides + consensus models (>= min_consensus sources)
    active_ids: list[str] = list(manual_by_id.keys())
    for cid, items in obs_by_model.items():
        distinct_sources = {i.source for i in items}
        if cid not in manual_by_id and len(distinct_sources) >= min_consensus:
            active_ids.append(cid)

    records: list[ModelRecord] = []
    total_sources = max(1, len(sources_meta))

    for idx, cid in enumerate(active_ids):
        items = obs_by_model.get(cid, [])
        distinct_sources = sorted({i.source for i in items})
        coverage_ratio = len(distinct_sources) / total_sources

        # Compute capability dimension scores via source dimension_weights * reliability
        dim_totals: dict[str, float] = {d: 0.0 for d in dimensions}
        dim_weights: dict[str, float] = {d: 0.0 for d in dimensions}

        for item in items:
            s_meta = sources_meta.get(item.source)
            if not s_meta:
                continue
            rel = float(s_meta.get("reliability", 1.0))
            cal_score = calibrated[(item.source, cid)]
            for dim, w in s_meta.get("dimension_weights", {}).items():
                if dim in dim_totals and w > 0:
                    dim_totals[dim] += cal_score * w * rel
                    dim_weights[dim] += w * rel

        observed_dims = {
            d: dim_totals[d] / dim_weights[d]
            for d in dimensions
            if dim_weights[d] > 0
        }

        manual = manual_by_id.get(cid)
        fallback_anchor = (
            mean(observed_dims.values())
            if observed_dims
            else (
                manual["steps"][1]["score"]
                if manual and len(manual.get("steps", [])) > 1
                else 45.0
            )
        )

        # Conservative imputation for missing dimensions (0.95x of model's observed mean)
        dim_scores: dict[str, float] = {}
        for d in dimensions:
            if d in observed_dims:
                dim_scores[d] = observed_dims[d]
            else:
                dim_scores[d] = fallback_anchor * 0.95

        # Compute task-profile scores
        profile_scores: dict[str, float] = {}
        for p_name, p_cfg in task_profiles.items():
            p_weights = p_cfg["weights"]
            if p_name == "trivial":
                # Trivial tasks factor in cost efficiency implicitly during recommendation
                val = sum(dim_scores.get(d, fallback_anchor) * w for d, w in p_weights.items())
            else:
                val = sum(dim_scores.get(d, fallback_anchor) * w for d, w in p_weights.items())
            profile_scores[p_name] = val

        # Build reasoning steps
        if manual:
            raw_steps = manual["steps"]
            name = manual["name"]
            provider = manual.get("provider", "unknown")
            harness = manual.get("harness", "api")
            is_codex = bool(manual.get("isCodex", False))
            color = manual.get("color", DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
        else:
            costs = [i.cost_usd for i in items if i.cost_usd is not None]
            anchor_cost = mean(costs) if costs else 0.75
            raw_steps = _synthesize_steps(anchor_cost, profile_scores["composite"])
            name = cid.replace("-", " ").title()
            provider, harness = _infer_provider_and_harness(cid)
            is_codex = harness == "codex-cli"
            color = DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]

        # Anchor Med step to calibrate profile_scores across Low/Med/High/Max
        med_step = next((s for s in raw_steps if s["level"] == "Med"), raw_steps[len(raw_steps) // 2])
        med_base = max(1.0, float(med_step["score"]))

        steps: list[ReasoningStep] = []
        for s in raw_steps:
            ratio = float(s["score"]) / med_base
            step_profiles = {
                p_name: round(p_val * ratio, 2)
                for p_name, p_val in profile_scores.items()
            }
            steps.append(
                ReasoningStep(
                    level=s["level"],
                    cost=float(s["cost"]),
                    score=float(s["score"]),
                    profile_scores=step_profiles,
                )
            )

        records.append(
            ModelRecord(
                id=cid,
                name=name,
                provider=provider,
                harness=harness,
                is_codex=is_codex,
                color=color,
                sources=distinct_sources if distinct_sources else ["manual"],
                coverage_ratio=coverage_ratio,
                dimension_scores=dim_scores,
                profile_scores=profile_scores,
                steps=steps,
            )
        )

    compute_pareto_flags(records, profile="composite")
    return records
