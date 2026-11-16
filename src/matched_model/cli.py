"""CLI entrypoint for matched_model."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from matched_model.pipeline import default_repo_root, run_pipeline
from matched_model.recommender import analyze_plan_markdown, recommend_model


def _load_benchmarks(root: Path) -> dict[str, Any]:
    bench_path = root / "data" / "benchmarks.json"
    if not bench_path.exists():
        return run_pipeline(repo_root=root, offline=True)
    with bench_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _cmd_update(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else default_repo_root()
    payload = run_pipeline(repo_root=root, offline=args.offline)
    print(f"Updated benchmarks.json ({len(payload['models'])} models) at {payload['lastUpdated']}")
    for src, info in payload["sourceStatus"].items():
        print(f"  - {src}: {info['status']} ({info['count']} obs) — {info['message']}")
    return 0


def _cmd_recommend(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else default_repo_root()
    data = _load_benchmarks(root)
    rec = recommend_model(
        models=data["models"],
        phase=args.phase,
        complexity=args.complexity,
        min_score=args.min_score,
        max_cost=args.max_cost,
        harness=args.harness,
        current_model_id=args.current_model,
    )
    out = {
        "phase": rec.phase,
        "complexity": rec.complexity,
        "profile_used": rec.profile_used,
        "min_score_required": rec.min_score_required,
        "max_cost_allowed": rec.max_cost_allowed,
        "primary": rec.primary,
        "alternative_budget": rec.alternative_budget,
        "alternative_high_assurance": rec.alternative_high_assurance,
        "diagnostics": rec.diagnostics,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if not rec.primary:
        print("No matching model found.")
        return 1

    p = rec.primary
    print(f"[matched-model] Phase={rec.phase} | Complexity={rec.complexity} | Profile={rec.profile_used} (floor={rec.min_score_required:.1f})")
    print(f"  Recommended : {p['name']} [{p['level']}] — ${p['cost']:.2f}/task, score {p['score']:.1f} (pareto={p['is_pareto']})")
    if rec.alternative_budget:
        b = rec.alternative_budget
        print(f"  Budget Alt  : {b['name']} [{b['level']}] — ${b['cost']:.2f}/task, score {b['score']:.1f}")
    if rec.alternative_high_assurance:
        h = rec.alternative_high_assurance
        print(f"  High Assur. : {h['name']} [{h['level']}] — ${h['cost']:.2f}/task, score {h['score']:.1f}")
    for d in rec.diagnostics:
        print(f"  Note        : {d}")
    return 0


def _cmd_plan_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else default_repo_root()
    data = _load_benchmarks(root)
    plan_path = Path(args.file)
    if not plan_path.exists():
        print(f"Plan file not found: {plan_path}", file=sys.stderr)
        return 1
    plan_text = plan_path.read_text(encoding="utf-8")
    rows = analyze_plan_markdown(plan_text, data["models"], harness=args.harness)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("| # | Phase | Complexity | Recommended Model | Tier | Cost/Task | Model Score | Reason | Task |")
    print("| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in rows:
        rec = r["recommended"] or {}
        name = rec.get("name", "N/A")
        level = rec.get("level", "-")
        cost = f"${rec['cost']:.2f}" if "cost" in rec else "-"
        score = f"{rec['score']:.1f}" if "score" in rec else "-"
        comp_label = f"{r['complexity']} ({r.get('complexity_score', '-')})"
        reason_str = ", ".join(r.get("reasons", []))
        task_short = (r["task"][:42] + "...") if len(r["task"]) > 45 else r["task"]
        print(f"| {r['step']} | {r['phase']} | {comp_label} | {name} | {level} | {cost} | {score} | {reason_str} | {task_short} |")
    return 0


def _cmd_install_skill(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else default_repo_root()
    skill_src = root / "skills" / "matched-model"
    if not skill_src.exists():
        print(f"Skill source not found: {skill_src}", file=sys.stderr)
        return 1

    home = Path.home()
    targets: dict[str, Path] = {}
    if args.scope == "global":
        targets = {
            "antigravity": home / ".gemini" / "config" / "skills" / "matched-model",
            "claude": home / ".claude" / "skills" / "matched-model",
            "codex": home / ".codex" / "skills" / "matched-model",
        }
    else:
        cwd = Path.cwd()
        targets = {
            "antigravity": cwd / ".agents" / "skills" / "matched-model",
            "claude": cwd / ".claude" / "skills" / "matched-model",
            "codex": cwd / ".codex" / "skills" / "matched-model",
        }

    selected = list(targets.keys()) if args.target == "all" else [args.target]
    for name in selected:
        dest = targets[name]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_src, dest)
        print(f"Installed matched-model skill for {name} -> {dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="matched-model", description="AI Model Right-Sizing & Benchmark CLI")
    parser.add_argument("--root", help="Override repository root directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_upd = sub.add_parser("update", help="Collect benchmarks and rebuild data/benchmarks.json")
    p_upd.add_argument("--offline", action="store_true", help="Use cached snapshot without network calls")
    p_upd.set_defaults(func=_cmd_update)

    p_rec = sub.add_parser("recommend", help="Recommend right-sized model for a task")
    p_rec.add_argument("--phase", default="implement", help="plan | implement | debug | review | test | trivial")
    p_rec.add_argument("--complexity", default="medium", help="trivial | low | medium | high | critical")
    p_rec.add_argument("--min-score", type=float, default=None)
    p_rec.add_argument("--max-cost", type=float, default=None)
    p_rec.add_argument("--harness", default=None, help="codex-cli | claude-code | gemini-cli | open-harness | all")
    p_rec.add_argument("--current-model", default=None, help="Check a candidate model for overkill/underkill")
    p_rec.add_argument("--json", action="store_true")
    p_rec.set_defaults(func=_cmd_recommend)

    p_plan = sub.add_parser("plan-check", help="Analyze a Markdown plan and output per-step model routing")
    p_plan.add_argument("--file", required=True, help="Path to plan markdown file")
    p_plan.add_argument("--harness", default=None)
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=_cmd_plan_check)

    p_sk = sub.add_parser("install-skill", help="Install SKILL.md into Antigravity, Claude Code, or Codex CLI")
    p_sk.add_argument("--target", choices=["antigravity", "claude", "codex", "all"], default="all")
    p_sk.add_argument("--scope", choices=["workspace", "global"], default="workspace")
    p_sk.set_defaults(func=_cmd_install_skill)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
