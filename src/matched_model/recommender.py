"""Right-sizing ('적정기술') model recommender and Plan -> Implement analyzer."""

from __future__ import annotations

import re
from typing import Any

from matched_model.models import Recommendation

COMPLEXITY_FLOORS: dict[str, float] = {
    "trivial": 24.0,
    "low": 40.0,
    "medium": 49.0,
    "high": 56.0,
    "critical": 62.0,
}

PHASE_TO_PROFILE: dict[str, str] = {
    "plan": "plan",
    "architect": "plan",
    "review": "plan",
    "implement": "implement",
    "code": "implement",
    "refactor": "implement",
    "debug": "debug",
    "fix": "debug",
    "test": "debug",
    "verify": "debug",
    "trivial": "trivial",
    "docs": "trivial",
}


def _candidate_score(step: dict[str, Any], profile: str) -> float:
    p_scores = step.get("profileScores") or {}
    if profile in p_scores:
        return float(p_scores[profile])
    return float(step.get("score", 0.0))


def recommend_model(
    models: list[dict[str, Any]],
    phase: str = "implement",
    complexity: str = "medium",
    min_score: float | None = None,
    max_cost: float | None = None,
    harness: str | None = None,
    current_model_id: str | None = None,
) -> Recommendation:
    """Recommend the most cost-effective (model, reasoning_level) clearing the quality floor."""
    phase_key = phase.lower().strip()
    comp_key = complexity.lower().strip()
    profile = PHASE_TO_PROFILE.get(phase_key, "composite")
    if comp_key == "trivial" and phase_key not in ("plan", "debug"):
        profile = "trivial"

    floor = min_score if min_score is not None else COMPLEXITY_FLOORS.get(comp_key, 49.0)

    candidates: list[dict[str, Any]] = []
    for m in models:
        if harness and harness != "all" and m.get("harness") != harness:
            continue
        for step in m.get("steps", []):
            score = _candidate_score(step, profile)
            cost = float(step["cost"])
            candidates.append(
                {
                    "id": m["id"],
                    "name": m["name"],
                    "harness": m.get("harness", "api"),
                    "level": step["level"],
                    "cost": cost,
                    "score": round(score, 2),
                    "composite_score": round(float(step["score"]), 2),
                    "is_pareto": bool(step.get("isPareto", False)),
                    "coverage_ratio": float(m.get("coverageRatio", 0.0)),
                }
            )

    if not candidates:
        return Recommendation(
            phase=phase_key,
            complexity=comp_key,
            profile_used=profile,
            min_score_required=floor,
            max_cost_allowed=max_cost,
            primary=None,
            alternative_budget=None,
            alternative_high_assurance=None,
            diagnostics=["No candidate models matched the harness filter."],
        )

    qualifying = [
        c
        for c in candidates
        if c["score"] >= floor and (max_cost is None or c["cost"] <= max_cost)
    ]

    diagnostics: list[str] = []
    if not qualifying:
        # Fallback: pick highest-scoring within max_cost (or overall) and warn
        pool = [c for c in candidates if max_cost is None or c["cost"] <= max_cost] or candidates
        pool.sort(key=lambda c: (-c["score"], c["cost"]))
        best = pool[0]
        diagnostics.append(
            f"Quality boundary warning: no model reached score >= {floor:.1f} "
            f"(best available is {best['name']} [{best['level']}] at {best['score']:.1f})."
        )
        return Recommendation(
            phase=phase_key,
            complexity=comp_key,
            profile_used=profile,
            min_score_required=floor,
            max_cost_allowed=max_cost,
            primary=best,
            alternative_budget=None,
            alternative_high_assurance=None,
            diagnostics=diagnostics,
        )

    # Right-sizing sort: lowest cost first, then Pareto-optimal, then higher score
    qualifying.sort(key=lambda c: (c["cost"], not c["is_pareto"], -c["score"], -c["coverage_ratio"]))
    primary = qualifying[0]

    # Budget alternative: cheapest candidate within 92% of floor (for relaxed tasks)
    relaxed_pool = [
        c
        for c in candidates
        if c["score"] >= floor * 0.92
        and c["cost"] < primary["cost"]
        and (max_cost is None or c["cost"] <= max_cost)
    ]
    relaxed_pool.sort(key=lambda c: (c["cost"], -c["score"]))
    alt_budget = relaxed_pool[0] if relaxed_pool else None

    # High-assurance alternative: next higher-scoring step
    higher_pool = [
        c
        for c in qualifying
        if c["score"] > primary["score"] + 1.5
    ]
    higher_pool.sort(key=lambda c: (c["cost"], -c["score"]))
    alt_high = higher_pool[0] if higher_pool else None

    # Overkill / Underkill check if caller passed current_model_id
    if current_model_id:
        curr_steps = [c for c in candidates if c["id"] == current_model_id]
        if curr_steps:
            curr_med = next((c for c in curr_steps if c["level"] == "Med"), curr_steps[0])
            if curr_med["score"] < floor:
                diagnostics.append(
                    f"UNDERKILL WARNING: {curr_med['name']} ({curr_med['score']:.1f}) is below "
                    f"the {floor:.1f} quality floor for {phase_key}/{comp_key}."
                )
            elif curr_med["cost"] > primary["cost"] * 2.5:
                ratio = curr_med["cost"] / max(0.01, primary["cost"])
                diagnostics.append(
                    f"OVERKILL WARNING: {curr_med['name']} (${curr_med['cost']:.2f}) costs "
                    f"{ratio:.1f}x more than right-sized {primary['name']} [{primary['level']}] "
                    f"(${primary['cost']:.2f})."
                )

    return Recommendation(
        phase=phase_key,
        complexity=comp_key,
        profile_used=profile,
        min_score_required=floor,
        max_cost_allowed=max_cost,
        primary=primary,
        alternative_budget=alt_budget,
        alternative_high_assurance=alt_high,
        diagnostics=diagnostics,
    )


def _classify_task_text(text: str) -> tuple[str, str]:
    """Heuristically classify a plan task line into (phase, complexity)."""
    lower = text.lower()
    if any(k in lower for k in ("architect", "design", "schema", "plan", "rfc", "trade-off", "설계", "아키텍처")):
        phase = "plan"
    elif any(k in lower for k in ("debug", "fix", "bug", "error", "incident", "test", "verify", "디버그", "테스트", "검증")):
        phase = "debug"
    elif any(k in lower for k in ("readme", "doc", "comment", "format", "lint", "typo", "문서", "주석")):
        phase = "trivial"
    else:
        phase = "implement"

    if any(k in lower for k in ("security", "auth", "migration", "concurrency", "distributed", "core", "critical", "보안", "마이그레이션")):
        complexity = "critical"
    elif any(k in lower for k in ("refactor", "pipeline", "engine", "integration", "multi-file", "리팩토링", "파이프라인", "엔진")):
        complexity = "high"
    elif phase == "trivial":
        complexity = "trivial"
    elif any(k in lower for k in ("simple", "helper", "config", "button", "css", "단순", "설정")):
        complexity = "low"
    else:
        complexity = "medium"

    return phase, complexity


def analyze_plan_markdown(
    plan_text: str,
    models: list[dict[str, Any]],
    harness: str | None = None,
) -> list[dict[str, Any]]:
    """Extract tasks from a Markdown plan and recommend a model+tier per task."""
    tasks: list[str] = []
    for line in plan_text.splitlines():
        stripped = line.strip()
        if re.match(r"^(#{2,4}\s+|[-*]\s+|\d+\.\s+)", stripped):
            clean = re.sub(r"^(#{2,4}\s+|[-*]\s+|\d+\.\s+)", "", stripped).strip()
            clean = re.sub(r"^\[[ xX]\]\s*", "", clean)
            if len(clean) >= 6:
                tasks.append(clean)

    results: list[dict[str, Any]] = []
    for idx, task in enumerate(tasks[:25], start=1):
        phase, complexity = _classify_task_text(task)
        rec = recommend_model(models, phase=phase, complexity=complexity, harness=harness)
        results.append(
            {
                "step": idx,
                "task": task,
                "phase": phase,
                "complexity": complexity,
                "profile": rec.profile_used,
                "recommended": rec.primary,
            }
        )
    return results
