# autoresearch

Autonomous iterative optimization for Claude Code. Generates standalone skills that run eval-driven improvement loops: hypothesize, modify, evaluate, commit/revert — repeating without human intervention until goals are met.

## Quick Start

```
/autoresearch "Improve test coverage to 80%"
```

## Commands

| Command | Description |
|---------|-------------|
| `/autoresearch "<goal>"` | Start an autonomous optimization loop |
| `/autoresearch-init "<domain>"` | Generate a skill without running the loop |
| `/autoresearch-status` | Check progress of active loops |
| `/autoresearch-resume` | Resume an interrupted loop |

## How It Works

1. **Discovery** — Detects your stack, asks 2-3 clarifying questions
2. **Skill Generation** — Creates a standalone skill in `.claude/skills/autoresearch-<slug>/`
3. **Baseline** — Runs evals against current state, creates experiment branch
4. **Autonomous Loop** — Iterates: analyze → hypothesize → modify → evaluate → commit/revert
5. **Completion** — Summarizes results, offers merge/keep/discard

## Architecture

### The Tripartite Design

- **Fixed Foundation** — `eval.json` + `eval_runner` define success criteria (immutable during loop)
- **Agent Playground** — Target files the agent may modify
- **Human Control Panel** — Skill files and eval config (edited between runs)

### Generated Skill Structure

```
.claude/skills/autoresearch-<slug>/
├── SKILL.md              # Self-contained optimization instructions
├── eval.json             # Binary pass/fail eval definitions
├── scripts/
│   ├── eval_runner.<ext> # Deterministic eval execution
│   └── loop_tracker.py   # Loop state machine
├── state.json            # Iteration state and hypothesis log
└── results/              # Per-iteration eval results
```

## Eval Types

| Type | Description | Example |
|------|-------------|---------|
| `exit_code_zero` | Command exits 0 | `pytest` passes |
| `output_contains` | Output includes string | Build prints "SUCCESS" |
| `output_not_contains` | Output excludes string | No "FAIL" in output |
| `regex_match` | Regex extracts value meeting threshold | Coverage >= 80% |
| `llm_judge` | Agent evaluates output against criteria | Code quality assessment |

## Strategies

- `coverage-improvement` — Increase test coverage
- `performance-optimization` — Reduce latency/resource usage
- `test-hardening` — Add edge cases and boundary tests
- `code-quality` — Improve linting scores
- `feature-completion` — Implement until acceptance tests pass
- `custom` — User-defined strategy

## Safety

- All work on an isolated experiment branch
- Only target files are modified; protected files are off-limits
- Improvements committed, regressions reverted
- Eval infrastructure is never modified during the loop
- Plateau detection prevents infinite loops
