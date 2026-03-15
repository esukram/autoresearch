# Runner Template

This is the template used by autoresearch to generate a standalone runner script (`runner.py`) that executes the optimization loop outside Claude Code using the Claude API directly.

## When to Generate

Generate `runner.py` alongside `eval_runner` and `loop_tracker` during Phase 2 (Skill Generation). The runner is always Python regardless of the project's script language, since it uses the Anthropic Python SDK.

## Template Variables

Same as [skill-template.md](skill-template.md), plus:

| Variable | Source | Example |
|----------|--------|---------|
| `{{SKILL_DIR}}` | Relative path from project root | `.claude/skills/autoresearch-test-coverage` |
| `{{EVAL_RUNNER_CMD}}` | Command to run eval_runner | `python3 .claude/skills/autoresearch-test-coverage/scripts/eval_runner.py` |

## Generated runner.py Template

```python
#!/usr/bin/env python3
"""
Standalone runner for autoresearch-{{SLUG}}.

Runs the autonomous optimization loop outside Claude Code using the Claude API.
Requires: pip install anthropic

Usage:
    python3 {{SKILL_DIR}}/scripts/runner.py [options]

Options:
    --max-iter N     Override max iterations (default: from eval.json)
    --resume         Resume from last checkpoint instead of starting fresh
    --dry-run        Validate config and print plan without executing
    --verbose        Print full Claude API responses
    --model MODEL    Claude model to use (default: sonnet)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
PROJECT_ROOT = Path.cwd()
EVAL_CONFIG = SKILL_DIR / "eval.json"
STATE_FILE = SKILL_DIR / "state.json"
RESULTS_DIR = SKILL_DIR / "results"
SKILL_MD = SKILL_DIR / "SKILL.md"

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "haiku": "claude-haiku-4-5-20251001",
}

# --- Tool definitions for Claude API ---

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Path must be relative to the project root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file from the project root",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Path must be relative to the project root. Only files matching target_files patterns are writable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file from the project root",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files matching a glob pattern relative to the project root.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., 'src/**/*.py', 'tests/*.js')",
                }
            },
            "required": ["pattern"],
        },
    },
]


# --- File safety checks ---


def matches_glob(path_str, patterns):
    """Check if a path matches any of the given glob patterns."""
    from fnmatch import fnmatch

    for pattern in patterns:
        if fnmatch(path_str, pattern):
            return True
        # Also check basename for simple patterns like "*.lock"
        if fnmatch(Path(path_str).name, pattern):
            return True
    return False


def validate_write(path_str, config):
    """Validate that a write is allowed by target_files/protected_files rules."""
    target_files = config.get("target_files", [])
    protected_files = config.get("protected_files", [])

    if not matches_glob(path_str, target_files):
        return False, f"BLOCKED: {path_str} is not in target_files {target_files}"
    if matches_glob(path_str, protected_files):
        return False, f"BLOCKED: {path_str} is in protected_files {protected_files}"
    return True, "OK"


# --- Tool execution ---


def execute_tool(name, input_data, config, verbose=False):
    """Execute a tool call and return the result string."""
    if name == "read_file":
        path = PROJECT_ROOT / input_data["path"]
        if not path.exists():
            return f"Error: file not found: {input_data['path']}"
        try:
            return path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"

    elif name == "write_file":
        path_str = input_data["path"]
        allowed, reason = validate_write(path_str, config)
        if not allowed:
            return reason
        path = PROJECT_ROOT / path_str
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(input_data["content"])
            return f"OK: wrote {len(input_data['content'])} bytes to {path_str}"
        except Exception as e:
            return f"Error writing file: {e}"

    elif name == "list_files":
        import glob as globmod

        pattern = input_data["pattern"]
        matches = sorted(globmod.glob(pattern, root_dir=str(PROJECT_ROOT), recursive=True))
        if not matches:
            return "No files matched the pattern."
        return "\n".join(matches[:200])  # Cap output

    return f"Unknown tool: {name}"


# --- State management ---


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "status": "not_started",
        "state": None,
        "iteration": 0,
        "baseline": None,
        "current": None,
        "best": None,
        "hypotheses": [],
        "plateau_counter": 0,
        "started_at": None,
        "last_updated": None,
    }


def save_state(state):
    state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


# --- Eval execution ---


def run_eval_runner(iteration):
    """Run eval_runner and return parsed results."""
    cmd = "{{EVAL_RUNNER_CMD}} " + str(iteration)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=600
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("ERROR: eval_runner timed out after 600s", file=sys.stderr)
        return None

    # Parse results file
    if iteration == 0:
        result_file = RESULTS_DIR / "baseline.json"
    else:
        result_file = RESULTS_DIR / f"iter-{iteration:03d}.json"

    if not result_file.exists():
        print(f"ERROR: results file not created: {result_file}", file=sys.stderr)
        return None

    return json.loads(result_file.read_text())


# --- Git operations ---


def git(*args):
    """Run a git command and return (success, stdout)."""
    result = subprocess.run(
        ["git"] + list(args), capture_output=True, text=True
    )
    return result.returncode == 0, result.stdout.strip()


def create_branch(slug):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    branch = f"autoresearch/{slug}-{timestamp}"
    ok, _ = git("checkout", "-b", branch)
    if not ok:
        print(f"ERROR: Failed to create branch {branch}", file=sys.stderr)
        sys.exit(1)
    return branch


def commit_changes(slug, iteration, hypothesis):
    git("add", "-A")
    msg = f"autoresearch({slug}): iter {iteration} — {hypothesis[:72]}"
    ok, _ = git("commit", "-m", msg)
    return ok


def revert_target_files(target_files):
    for pattern in target_files:
        git("checkout", "--", pattern)
    # Also clean any untracked files in target dirs
    git("checkout", "--", ".")


# --- Context builder ---


def build_system_prompt(config, state, last_results):
    """Build the system prompt for Claude with full context."""
    skill_md = SKILL_MD.read_text() if SKILL_MD.exists() else ""
    eval_json = json.dumps(json.loads(EVAL_CONFIG.read_text()), indent=2)

    hypothesis_log = ""
    if state["hypotheses"]:
        recent = state["hypotheses"][-10:]  # Last 10
        hypothesis_log = "\n".join(
            f"- iter {h['iteration']}: {h['hypothesis']} → {h['result']}"
            for h in recent
        )

    results_section = ""
    if last_results:
        results_section = json.dumps(last_results, indent=2)

    return f"""You are an autonomous code optimization agent. Your goal is to improve code to pass all evals.

## Skill Definition
{skill_md}

## Eval Configuration
{eval_json}

## Current State
- Iteration: {state['iteration']}
- Passing: {state['current']['pass_count']}/{state['current']['total'] if state['current'] else 'N/A'}
- Best: {state['best']['pass_count']}/{state['best']['total'] if state['best'] else 'N/A'} (iter {state['best']['iteration'] if state['best'] else 'N/A'})
- Plateau counter: {state['plateau_counter']}

## Last Eval Results
{results_section}

## Hypothesis Log (recent)
{hypothesis_log}

## Instructions

You are in the ANALYZE → HYPOTHESIZE → MODIFY phase.

1. ANALYZE: Read the eval results above. Identify which evals are failing and why.
   Use read_file to examine the relevant source code and test output.

2. HYPOTHESIZE: Form a specific, testable hypothesis about what change will fix a failing eval.
   State your hypothesis clearly before making changes.
   Check the hypothesis log — do NOT repeat previously failed approaches.

3. MODIFY: Use write_file to implement your hypothesis.
   - Only modify files matching the target_files patterns.
   - Make minimal, focused changes.
   - Do not modify eval.json, eval_runner, or SKILL.md.

When you have finished your modifications, stop and say "MODIFICATIONS COMPLETE" followed by a one-line summary of your hypothesis.

If you believe no further improvements are possible, say "NO_FURTHER_IMPROVEMENTS" and explain why."""


# --- Main loop ---


def run_iteration(client, model, config, state, last_results, verbose=False):
    """Run one ANALYZE → HYPOTHESIZE → MODIFY iteration via Claude API."""
    system_prompt = build_system_prompt(config, state, last_results)

    messages = [
        {
            "role": "user",
            "content": "Analyze the current eval results and make targeted modifications to improve passing evals. Begin.",
        }
    ]

    # Conversation loop — Claude may call tools multiple times
    for turn in range(50):  # Safety cap on turns
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if verbose:
            print(f"\n--- Claude turn {turn + 1} ---")
            for block in response.content:
                if hasattr(block, "text"):
                    print(block.text)
                elif block.type == "tool_use":
                    print(f"[tool: {block.name}({json.dumps(block.input)[:200]})]")

        # Collect text and tool calls
        assistant_content = response.content
        hypothesis = None

        # Check for termination signals in text blocks
        for block in assistant_content:
            if hasattr(block, "text"):
                if "MODIFICATIONS COMPLETE" in block.text:
                    # Extract hypothesis from the line after the signal
                    lines = block.text.split("MODIFICATIONS COMPLETE")
                    if len(lines) > 1:
                        hypothesis = lines[1].strip().split("\n")[0].strip(" :")
                    return hypothesis or "modifications applied"
                if "NO_FURTHER_IMPROVEMENTS" in block.text:
                    return None  # Signal to stop

        # If stop_reason is end_turn with no tool use, Claude is done talking
        if response.stop_reason == "end_turn":
            # Extract any hypothesis from the text
            for block in assistant_content:
                if hasattr(block, "text"):
                    text = block.text
                    # Look for hypothesis-like statements
                    for line in text.split("\n"):
                        if line.strip().startswith("Hypothesis:"):
                            hypothesis = line.strip().removeprefix("Hypothesis:").strip()
                    if not hypothesis and len(text) > 20:
                        hypothesis = text[:100]
            return hypothesis or "iteration complete"

        # Process tool calls
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    result = execute_tool(
                        block.name, block.input, config, verbose
                    )
                    if verbose:
                        preview = result[:200] + "..." if len(result) > 200 else result
                        print(f"  → {preview}")
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason
            break

    return "max turns reached"


def main():
    parser = argparse.ArgumentParser(
        description="Standalone autoresearch runner for {{SLUG}}"
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=None,
        help="Override max iterations",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and print plan without executing",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full Claude API responses",
    )
    parser.add_argument(
        "--model",
        default="sonnet",
        help="Model alias (sonnet, opus, haiku) or full model ID",
    )
    args = parser.parse_args()

    # --- Startup checks ---

    # Check for anthropic package
    try:
        import anthropic
    except ImportError:
        print("ERROR: The 'anthropic' package is required.", file=sys.stderr)
        print("Install it with: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # Load config
    if not EVAL_CONFIG.exists():
        print(f"ERROR: eval.json not found at {EVAL_CONFIG}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(EVAL_CONFIG.read_text())["config"]
    eval_data = json.loads(EVAL_CONFIG.read_text())
    max_iterations = args.max_iter or config.get("max_iterations", 50)
    plateau_threshold = config.get("plateau_threshold", 5)
    slug = "{{SLUG}}"

    # Resolve model
    model = MODEL_ALIASES.get(args.model, args.model)

    # --- Dry run ---

    if args.dry_run:
        print(f"=== Dry Run: autoresearch-{slug} ===")
        print(f"Model:          {model}")
        print(f"Max iterations: {max_iterations}")
        print(f"Plateau limit:  {plateau_threshold}")
        print(f"Target files:   {config.get('target_files', [])}")
        print(f"Protected files:{config.get('protected_files', [])}")
        print(f"Evals:          {len(eval_data['evals'])}")
        for e in eval_data["evals"]:
            print(f"  - {e['id']}: {e['description']}")
        print(f"\nSkill dir:      {SKILL_DIR}")
        print(f"API key:        ...{api_key[-4:]}")
        print("\nConfig is valid. Ready to run.")
        sys.exit(0)

    # --- Initialize ---

    client = anthropic.Anthropic(api_key=api_key)
    state = load_state()

    if args.resume and state["status"] == "running":
        print(f"Resuming from iteration {state['iteration']}")
    else:
        # Fresh start
        state = load_state()  # Reset
        state["status"] = "running"
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        save_state(state)

        # Create experiment branch
        branch = create_branch(slug)
        print(f"Created branch: {branch}")

        # Run baseline
        print("\n=== Running Baseline ===")
        baseline = run_eval_runner(0)
        if not baseline:
            print("ERROR: Baseline eval failed", file=sys.stderr)
            sys.exit(1)

        state["baseline"] = {
            "pass_count": baseline["pass_count"],
            "fail_count": baseline["fail_count"],
            "total": baseline["total"],
        }
        state["current"] = dict(state["baseline"])
        state["best"] = {**state["baseline"], "iteration": 0}
        save_state(state)

        # Commit skill files
        git("add", str(SKILL_DIR))
        git("commit", "-m", f"autoresearch({slug}): initialize skill and baseline")

        print(
            f"Baseline: {baseline['pass_count']}/{baseline['total']} evals passing"
        )

        if baseline["pass_count"] == baseline["total"]:
            print("\nAll evals already pass! Nothing to optimize.")
            state["status"] = "complete"
            save_state(state)
            sys.exit(0)

    # --- Main loop ---

    last_results = None
    # Load latest results file
    if state["iteration"] > 0:
        result_file = RESULTS_DIR / f"iter-{state['iteration']:03d}.json"
        if result_file.exists():
            last_results = json.loads(result_file.read_text())
    if not last_results:
        baseline_file = RESULTS_DIR / "baseline.json"
        if baseline_file.exists():
            last_results = json.loads(baseline_file.read_text())

    print(f"\n=== Starting Optimization Loop (max {max_iterations} iterations) ===\n")

    while state["iteration"] < max_iterations:
        iteration = state["iteration"] + 1
        state["iteration"] = iteration
        state["state"] = "analyze"
        save_state(state)

        print(f"--- Iteration {iteration}/{max_iterations} ---")

        # ANALYZE + HYPOTHESIZE + MODIFY (via Claude API)
        state["state"] = "modify"
        save_state(state)

        hypothesis = run_iteration(
            client, model, config, state, last_results, args.verbose
        )

        if hypothesis is None:
            print("Claude indicates no further improvements possible.")
            state["status"] = "exhausted"
            state["state"] = "done"
            save_state(state)
            break

        # Log hypothesis
        state["hypotheses"].append(
            {
                "iteration": iteration,
                "hypothesis": hypothesis,
                "target_eval": "auto",
                "target_files": config.get("target_files", []),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "result": None,
            }
        )
        save_state(state)

        print(f"  Hypothesis: {hypothesis[:80]}")

        # EVALUATE
        state["state"] = "evaluate"
        save_state(state)

        results = run_eval_runner(iteration)
        if not results:
            print("  ERROR: eval_runner failed, reverting")
            revert_target_files(config.get("target_files", []))
            state["hypotheses"][-1]["result"] = "error"
            state["plateau_counter"] += 1
            save_state(state)
            continue

        last_results = results

        # DECIDE
        state["state"] = "decide"
        save_state(state)

        prev_pass = state["current"]["pass_count"] if state["current"] else 0
        new_pass = results["pass_count"]

        if new_pass > prev_pass:
            # Improvement — commit
            committed = commit_changes(slug, iteration, hypothesis)
            state["current"] = {
                "pass_count": new_pass,
                "fail_count": results["fail_count"],
                "total": results["total"],
            }
            state["plateau_counter"] = 0
            if new_pass > (state["best"]["pass_count"] if state["best"] else 0):
                state["best"] = {**state["current"], "iteration": iteration}
            state["hypotheses"][-1]["result"] = "committed"
            print(f"  COMMIT: {new_pass}/{results['total']} passing (+{new_pass - prev_pass})")
        else:
            # Regression or neutral — revert
            revert_target_files(config.get("target_files", []))
            state["plateau_counter"] += 1
            state["hypotheses"][-1]["result"] = "reverted"
            print(f"  REVERT: {new_pass}/{results['total']} (no improvement)")

        save_state(state)

        # Check termination conditions
        if new_pass == results["total"]:
            print(f"\nAll evals pass! Completed in {iteration} iterations.")
            state["status"] = "complete"
            state["state"] = "done"
            save_state(state)
            break

        if state["plateau_counter"] >= plateau_threshold:
            print(f"\nPlateau detected ({plateau_threshold} iterations without improvement).")
            state["status"] = "plateau"
            state["state"] = "done"
            save_state(state)
            break
    else:
        print(f"\nMax iterations ({max_iterations}) reached.")
        state["status"] = "max_iterations"
        state["state"] = "done"
        save_state(state)

    # --- Report ---

    print("\n=== Results ===")
    print(f"Status:     {state['status']}")
    print(f"Iterations: {state['iteration']}")
    commits = sum(1 for h in state["hypotheses"] if h["result"] == "committed")
    reverts = sum(1 for h in state["hypotheses"] if h["result"] == "reverted")
    print(f"Commits:    {commits}")
    print(f"Reverts:    {reverts}")
    if state["baseline"] and state["current"]:
        print(
            f"Baseline:   {state['baseline']['pass_count']}/{state['baseline']['total']}"
        )
        print(
            f"Final:      {state['current']['pass_count']}/{state['current']['total']}"
        )
    if state["best"]:
        print(
            f"Best:       {state['best']['pass_count']}/{state['best']['total']} (iter {state['best']['iteration']})"
        )

    # Show diff
    ok, diff = git("diff", "main...HEAD", "--stat")
    if ok and diff:
        print(f"\nChanges:\n{diff}")


if __name__ == "__main__":
    main()
```
