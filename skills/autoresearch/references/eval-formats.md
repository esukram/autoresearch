# Eval Config Format Specification

This document defines the `eval.json` schema used by autoresearch generated skills.

## Schema

```json
{
  "version": 1,
  "goal": "<string: natural language description of the optimization goal>",
  "evals": [
    {
      "id": "<string: unique identifier, kebab-case>",
      "description": "<string: human-readable description of what this eval checks>",
      "command": "<string: shell command to execute>",
      "pass_condition": { "<pass_condition object>" },
      "required": "<boolean: whether this eval must pass for the loop to succeed>",
      "timeout_seconds": "<number: optional per-eval timeout override>"
    }
  ],
  "config": {
    "max_iterations": "<number: maximum loop iterations, default 50>",
    "timeout_per_eval_seconds": "<number: default timeout per eval, default 120>",
    "timeout_per_iteration_seconds": "<number: max time per full iteration, default 600>",
    "target_files": ["<string: glob patterns for files the agent may modify>"],
    "protected_files": ["<string: glob patterns for files the agent must not modify>"],
    "strategy_hint": "<string: optimization strategy identifier>",
    "plateau_threshold": "<number: consecutive no-improvement iterations before stopping, default 5>",
    "script_language": "<string: language for generated scripts (python|javascript|shell)>"
  }
}
```

## Pass Condition Types

### `exit_code_zero`

The simplest condition: the command must exit with code 0.

```json
{
  "type": "exit_code_zero"
}
```

**Use for:** test suites, linters, type checkers, build commands — anything where exit code 0 means success.

### `output_contains`

The command's combined stdout+stderr must contain a specific string.

```json
{
  "type": "output_contains",
  "value": "All checks passed"
}
```

**Use for:** tools that print a success message but may exit 0 regardless.

### `output_not_contains`

The command's output must NOT contain a specific string.

```json
{
  "type": "output_not_contains",
  "value": "FAIL"
}
```

**Use for:** tools that print failure markers in otherwise-passing output.

### `regex_match`

Extract a numeric value from output using a regex and compare it against a threshold.

```json
{
  "type": "regex_match",
  "pattern": "TOTAL\\s+\\d+\\s+\\d+\\s+(\\d+)%",
  "group": 1,
  "operator": ">=",
  "threshold": 80
}
```

**Fields:**
- `pattern` — Regex with at least one capture group
- `group` — Which capture group to extract (1-indexed)
- `operator` — Comparison operator: `>=`, `>`, `<=`, `<`, `==`, `!=`
- `threshold` — Numeric value to compare against

**Use for:** coverage percentages, performance metrics, scores, counts.

### `llm_judge`

The agent evaluates the command output against specified criteria. This is the only non-deterministic pass condition and should be used sparingly.

```json
{
  "type": "llm_judge",
  "criteria": "The API response contains well-structured JSON with all required fields: id, name, email, created_at. The response should not contain any PII beyond what was requested.",
  "pass_description": "Response is well-structured and contains exactly the expected fields",
  "fail_description": "Response is malformed, missing fields, or contains unexpected PII"
}
```

**Fields:**
- `criteria` — Natural language description of what constitutes a pass
- `pass_description` — What a passing result looks like (helps calibration)
- `fail_description` — What a failing result looks like (helps calibration)

**Use for:** output quality, code style assessment, documentation completeness — subjective metrics that can't be captured by regex.

**Caution:** LLM-as-judge introduces non-determinism. The same code may pass or fail on different runs. Use only when no deterministic alternative exists.

## Examples by Domain

### Python Test Coverage

```json
{
  "version": 1,
  "goal": "Increase test coverage to 80% while keeping all tests passing",
  "evals": [
    {
      "id": "tests-pass",
      "description": "All existing tests pass without error",
      "command": "pytest --tb=short -q",
      "pass_condition": { "type": "exit_code_zero" },
      "required": true
    },
    {
      "id": "no-test-errors",
      "description": "No test collection errors",
      "command": "pytest --collect-only -q 2>&1",
      "pass_condition": { "type": "output_not_contains", "value": "ERROR" },
      "required": true
    },
    {
      "id": "coverage-target",
      "description": "Code coverage is at least 80%",
      "command": "pytest --cov=src --cov-report=term -q",
      "pass_condition": {
        "type": "regex_match",
        "pattern": "TOTAL\\s+\\d+\\s+\\d+\\s+(\\d+)%",
        "group": 1,
        "operator": ">=",
        "threshold": 80
      },
      "required": true
    }
  ],
  "config": {
    "max_iterations": 50,
    "timeout_per_eval_seconds": 120,
    "target_files": ["tests/**/*.py"],
    "protected_files": ["src/**/*.py", "setup.py", "pyproject.toml", "*.lock"],
    "strategy_hint": "coverage-improvement",
    "plateau_threshold": 5,
    "script_language": "python"
  }
}
```

### Node.js API Performance

```json
{
  "version": 1,
  "goal": "Reduce average API response time to under 100ms",
  "evals": [
    {
      "id": "tests-pass",
      "description": "All existing tests pass",
      "command": "npm test",
      "pass_condition": { "type": "exit_code_zero" },
      "required": true
    },
    {
      "id": "type-check",
      "description": "TypeScript compilation succeeds",
      "command": "npx tsc --noEmit",
      "pass_condition": { "type": "exit_code_zero" },
      "required": true
    },
    {
      "id": "latency-target",
      "description": "Average response time under 100ms",
      "command": "node scripts/benchmark.js",
      "pass_condition": {
        "type": "regex_match",
        "pattern": "avg_response_ms:\\s*(\\d+\\.?\\d*)",
        "group": 1,
        "operator": "<=",
        "threshold": 100
      },
      "required": true
    }
  ],
  "config": {
    "max_iterations": 30,
    "timeout_per_eval_seconds": 60,
    "timeout_per_iteration_seconds": 300,
    "target_files": ["src/routes/**/*.ts", "src/middleware/**/*.ts"],
    "protected_files": ["package.json", "tsconfig.json", "*.lock", "tests/**/*"],
    "strategy_hint": "performance-optimization",
    "plateau_threshold": 5,
    "script_language": "javascript"
  }
}
```

### Go Edge Case Tests

```json
{
  "version": 1,
  "goal": "Add edge case tests until all boundary conditions are covered",
  "evals": [
    {
      "id": "tests-pass",
      "description": "All Go tests pass",
      "command": "go test ./... -count=1",
      "pass_condition": { "type": "exit_code_zero" },
      "required": true
    },
    {
      "id": "race-check",
      "description": "No data races detected",
      "command": "go test -race ./... -count=1",
      "pass_condition": { "type": "exit_code_zero" },
      "required": true
    },
    {
      "id": "coverage-minimum",
      "description": "Test coverage at least 90%",
      "command": "go test -coverprofile=cover.out ./... && go tool cover -func=cover.out | tail -1",
      "pass_condition": {
        "type": "regex_match",
        "pattern": "(\\d+\\.\\d+)%",
        "group": 1,
        "operator": ">=",
        "threshold": 90
      },
      "required": true
    }
  ],
  "config": {
    "max_iterations": 40,
    "timeout_per_eval_seconds": 120,
    "target_files": ["**/*_test.go"],
    "protected_files": ["go.mod", "go.sum", "**/*.go", "!**/*_test.go"],
    "strategy_hint": "test-hardening",
    "plateau_threshold": 5,
    "script_language": "shell"
  }
}
```

## Eval Design Guidelines

### Required vs Optional Evals

- **Required evals** (`"required": true`): Must ALL pass for the loop to succeed. These are non-negotiable constraints (e.g., "tests pass", "no regressions").
- **Optional evals** (`"required": false`): Improvements tracked but not required. Useful for stretch goals.

The loop completes successfully when all required evals pass.

### Eval Ordering

Evals are run in array order. Place fast, likely-to-fail evals first for quick feedback:

1. Syntax/compilation checks (fast, catches broken code)
2. Existing test suite (medium, catches regressions)
3. Target metric (may be slow, this is what we're optimizing)

### Eval Independence

Each eval should be independently runnable. Avoid evals that depend on side effects from previous evals. If evals share setup, put the setup in each command.

### Avoiding Flaky Evals

- Use deterministic seeds where possible
- Set explicit timeouts
- Avoid network-dependent evals in tight loops
- For performance evals, use multiple runs and averages
- Reserve `llm_judge` for when no deterministic option exists
