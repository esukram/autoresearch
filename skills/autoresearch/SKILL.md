---
name: autoresearch
description: >
  Autonomous iterative optimization through eval-driven loops. Use when:
  (1) User wants to autonomously optimize code against measurable goals,
  (2) User asks for an eval loop, optimization loop, or iterative improvement,
  (3) User wants to auto-optimize test coverage, performance, or code quality,
  (4) User wants eval-driven or hill-climbing optimization,
  (5) User describes a measurable goal and wants autonomous iteration toward it.
  Triggers on keywords: "autoresearch", "optimization loop", "eval loop",
  "iterative improvement", "auto-optimize", "eval-driven", "hill climbing",
  "autonomous optimization", "eval set", "binary eval".
user-invocable: false
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent
---

# Autoresearch

You are an autonomous iterative optimization engine. You generate standalone skills that run eval-driven improvement loops: hypothesize → modify → evaluate → commit/revert — repeating without human intervention until goals are met or limits reached.

## What Autoresearch Is

Autoresearch is an **autonomous iterative optimization paradigm**. Given a measurable goal (improve coverage, reduce latency, pass edge-case tests), it:

1. Generates a **standalone, portable skill** tailored to the user's domain
2. Establishes a **baseline** by running evals against the current state
3. Runs an **autonomous loop** that repeatedly improves the code
4. **Commits improvements** and **reverts regressions** automatically
5. Stops when goals are met, iteration limits reached, or progress plateaus

The core insight: optimization is most effective when the agent can iterate freely against deterministic, binary pass/fail metrics — without waiting for human review at each step.

## The Tripartite Architecture

Every autoresearch skill separates concerns into three zones:

### 1. Fixed Foundation (Immutable During Loop)

- **`eval.json`** — Defines the eval set: what to measure, how to measure it, what "pass" means
- **`scripts/eval_runner`** — Executes evals deterministically and reports results

These are **never modified by the agent during the loop**. They are the ground truth. If evals need changing, the human updates them between runs.

### 2. Agent Playground (Modified by Agent)

- **Target files** — The only files the agent may modify during the loop
- Defined by `config.target_files` glob patterns in eval.json
- Everything outside this set is off-limits

### 3. Human Control Panel (Modified by Human)

- **The skill files themselves** — SKILL.md, eval.json, scripts
- **Iterated by the human between runs** — adjust evals, change targets, refine strategy
- The agent proposes but the human disposes (between runs)

This separation ensures the agent has clear boundaries: it optimizes within its playground, measured against an immutable foundation, guided by human-defined goals.

## How It Works

### For the user

1. Run `/autoresearch "<goal>"` with a natural language description
2. Answer 2-3 clarifying questions about target files, eval commands, and script language
3. Autoresearch generates a complete standalone skill in `.claude/skills/autoresearch-<slug>/`
4. The loop runs autonomously — no further input needed
5. Review results when complete: diff, summary, merge/keep/discard

### For the agent

1. **Discovery** — Parse goal, detect stack, determine eval strategy
2. **Skill generation** — Create SKILL.md, eval.json, scripts in the user's project
3. **Baseline** — Run evals, record starting point, create experiment branch
4. **Autonomous loop** — Follow [loop-protocol.md](references/loop-protocol.md) without pausing
5. **Completion** — Summarize results, present options

## Workflow Overview

The primary entry point is the `/autoresearch` command. Supporting commands:

- **`/autoresearch "<goal>"`** — Full workflow: discover → generate → baseline → loop → complete
- **`/autoresearch-init "<domain>"`** — Generate the skill without running the loop (for review/customization)
- **`/autoresearch-resume`** — Resume an interrupted loop from its last checkpoint
- **`/autoresearch-status`** — Check progress of a running or completed loop

## Generated Skill Structure

Each generated skill is self-contained and portable:

```
.claude/skills/autoresearch-<slug>/
├── SKILL.md              # Self-contained skill with embedded loop protocol
├── eval.json             # Binary eval set definitions
├── scripts/
│   ├── eval_runner.<ext> # Deterministic eval execution
│   └── loop_tracker.<ext># State machine for the optimization loop
├── state.json            # Loop state (iteration, scores, hypotheses)
└── results/
    ├── baseline.json     # Initial eval results
    ├── iter-001.json     # Per-iteration results
    └── ...
```

## Eval Config Format

Reference: [eval-formats.md](references/eval-formats.md) for full specification.

The `eval.json` file defines what success looks like:

```json
{
  "version": 1,
  "goal": "<natural language goal>",
  "evals": [
    {
      "id": "<unique-id>",
      "description": "<what this eval checks>",
      "command": "<shell command to run>",
      "pass_condition": { "type": "<condition_type>", ... },
      "required": true
    }
  ],
  "config": {
    "max_iterations": 50,
    "timeout_per_eval_seconds": 120,
    "timeout_per_iteration_seconds": 600,
    "target_files": ["<glob patterns>"],
    "protected_files": ["<glob patterns>"],
    "strategy_hint": "<domain strategy>",
    "plateau_threshold": 5
  }
}
```

**Pass condition types:**
- `exit_code_zero` — Command exits with code 0
- `output_contains` — Output contains a string
- `output_not_contains` — Output does not contain a string
- `regex_match` — Regex captures a value that meets a numeric threshold
- `llm_judge` — Agent evaluates output against criteria (for subjective metrics)

## The Autonomous Loop

Reference: [loop-protocol.md](references/loop-protocol.md) for the full state machine protocol.

**State machine:** `INIT → ANALYZE → HYPOTHESIZE → MODIFY → EVALUATE → DECIDE → [ANALYZE | DONE]`

```
REPEAT until all_evals_pass OR iteration >= max_iterations OR plateau:
  1. ANALYZE    — Read last eval results, identify failing evals
  2. HYPOTHESIZE — Form testable hypothesis, log it
  3. MODIFY     — Implement change in target files ONLY
  4. EVALUATE   — Run eval_runner, collect results
  5. DECIDE     — Improvement → git commit; Regression/Neutral → git revert
```

Key properties:
- **Deterministic evaluation** — Same code always produces same eval results
- **Monotonic progress** — Only improvements are committed; regressions are reverted
- **Bounded execution** — Max iterations and plateau detection prevent infinite loops
- **Full traceability** — Every hypothesis, modification, and result is logged

## Domain Strategies

Reference: [domain-strategies.md](references/domain-strategies.md) for optimization strategies per domain.

The `strategy_hint` in eval.json guides optimization approach:

- **`coverage-improvement`** — Add tests to increase code coverage
- **`performance-optimization`** — Reduce latency, memory, or resource usage
- **`test-hardening`** — Add edge cases, error handling, boundary tests
- **`code-quality`** — Improve linting scores, reduce complexity
- **`feature-completion`** — Implement features until acceptance tests pass
- **`custom`** — User-defined strategy with explicit hints

## Script Language Selection

Generated skills use the domain-appropriate language:

| Project Stack | Script Language | Rationale |
|---------------|-----------------|-----------|
| Python        | Python          | Native tooling (pytest, coverage) |
| Node.js/TS    | JavaScript      | Native tooling (jest, vitest) |
| Go            | Shell + Go      | `go test` is CLI-first |
| Rust          | Shell + Rust    | `cargo test` is CLI-first |
| Other         | Shell (bash)    | Universal baseline |

Language is confirmed with the user during discovery.

## Core Enforcement Rules

These rules are **non-negotiable** during autonomous loop execution:

1. **Never modify eval.json or eval_runner during the loop** — These are the ground truth. If they're wrong, the human fixes them between runs.
2. **Only modify target_files** — Everything else is read-only. Protected files are explicitly forbidden.
3. **Commit improvements, revert regressions** — No exceptions. The codebase only moves forward.
4. **Log every hypothesis** — Before modifying code, write what you expect to happen and why.
5. **Respect iteration limits** — Stop at max_iterations even if goals aren't met.
6. **Detect plateaus** — If N consecutive iterations show no improvement, stop and report.
7. **No interactive prompts during loop** — The loop runs autonomously. If you need human input, stop the loop and report.
8. **Preserve the experiment branch** — All loop work happens on a dedicated branch. Never modify main/master during the loop.

Reference: [safety-rules.md](references/safety-rules.md) for comprehensive guardrails.

## When to Use Autoresearch

**Good fit:**
- Measurable goals with deterministic evaluation (test pass rates, coverage %, latency benchmarks)
- Repetitive optimization that benefits from many iterations
- Well-defined target files and clear eval criteria
- Goals where incremental progress is meaningful

**Poor fit:**
- Subjective quality with no measurable proxy (unless using llm_judge)
- Tasks requiring architectural changes across many files
- Goals that can't be evaluated automatically
- One-shot tasks that don't benefit from iteration

## When Not to Use

- If the goal can be achieved in a single focused edit, just do it
- If evaluation requires manual testing or visual inspection (with no automated proxy)
- If the target files are unclear or span the entire codebase
- If the project has no test infrastructure and adding it is the real task (use TDD coach instead)

## Skill Template

Reference: [skill-template.md](references/skill-template.md) for the template used to generate domain-specific skills.

Generated skills follow this template, customized with:
- Domain-specific SKILL.md instructions
- Appropriate eval.json with domain-relevant pass conditions
- Scripts in the project's language
- Strategy-specific analysis and hypothesis guidance
