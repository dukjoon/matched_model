---
name: matched-model
description: >-
  Right-sizes AI models and reasoning tiers (Low/Med/High/Max) for Plan -> Implement
  workflows using domain-calibrated multi-benchmark scores (DeepSWE, Artificial Analysis,
  SWE-bench, LiveBench, Aider, Terminal-Bench, LMSYS). Use before executing a plan to
  prevent both expensive over-provisioning and quality-degrading under-provisioning.
---

# `matched-model` — Plan → Implement Model Right-Sizing Gate

You have access to the `matched-model` benchmark & routing system. Your goal is to ensure every task in a **`plan => implement => verify`** workflow uses the **most cost-efficient model and reasoning tier that safely clears the task's quality boundary** ("적정기술").

## When to Activate
1. **Plan → Implement Transition**: Right after drafting or reading an implementation plan (`implementation_plan.md`, task checklist, or multi-step prompt), before writing code.
2. **Model Selection Check**: When the user asks which model or reasoning level (`Low`, `Med`, `High`, `Max`) to use, or when a subagent/worker is about to be dispatched.

## Workflow

### Step 1: Analyze the Plan's Steps
Break the plan into discrete steps and classify each step along two axes:
- **`phase`**:
  - `plan` (architecture, schema design, trade-off analysis, code review)
  - `implement` (feature coding, multi-file refactoring, API endpoints)
  - `debug` (bug reproduction, root-cause analysis, test/CI verification, shell/devops)
  - `trivial` (docs, comments, formatting, simple config)
- **`complexity`**: `trivial` | `low` | `medium` | `high` | `critical`

### Step 2: Query `matched-model`
Run the CLI if available in the workspace (or read `data/routing_rules.json` directly as a zero-dependency fallback):

```bash
# For an entire plan markdown file:
matched-model plan-check --file path/to/plan.md

# For a single step (optionally checking against a currently selected model):
matched-model recommend --phase implement --complexity medium --current-model claude-opus-5.5
```

If `matched-model` is not on `PATH`, run:
```bash
PYTHONPATH=src python3 -m matched_model.cli recommend --phase <phase> --complexity <complexity>
```

### Step 3: Present a Model Routing Table & Flag Boundaries
Before starting implementation, output a concise **Model Routing Table**:
- Highlight any **OVERKILL** (e.g., using a $6–$11 flagship `High/Max` model for a `trivial`/`low` task where a $0.04–$0.65 tier clears the quality floor).
- Highlight any **UNDERKILL** (e.g., using a budget `Low` model on a `critical` security/architecture/migration task where it falls below the quality floor).
- Note that rankings are **domain-weighted** (e.g., `plan` prioritizes `reasoning_planning` + `agentic_swe`, whereas `implement` prioritizes `code_generation` + `agentic_swe`), not naive averages.
