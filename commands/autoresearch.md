---
name: autoresearch
description: Start an autonomous optimization loop for a given goal
argument-hint: "<goal>"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent
---

# /autoresearch

You are running the autoresearch autonomous optimization loop. Follow each phase in order. Do not skip phases. Do not pause for user input except during Phase 1 discovery.

Load the core skill for reference: [SKILL.md](../skills/autoresearch/SKILL.md)

## Phase 1: Discovery

Parse the user's goal: `$ARGUMENTS`

1. **Detect the project stack:**
   - Examine the project root for language markers (package.json, pyproject.toml, go.mod, Cargo.toml, etc.)
   - Identify: language, package manager, test framework, test command
   - If ambiguous, ask the user to confirm

2. **Ask 2-3 clarifying questions** (batch them in one message):
   - **Target files:** Which files should the agent modify? Propose sensible defaults based on the goal and stack.
   - **Eval commands:** What commands evaluate success? Propose defaults based on the goal (e.g., `pytest --cov` for coverage).
   - **Protected files:** Any files that must not be modified? Propose defaults (source files if only adding tests, config files, lock files).
   - **Script language:** Confirm the language for generated scripts (default: match project language).
   - **Iteration limit:** Confirm max iterations (default: 50).

3. **Determine strategy:**
   - Map the goal to a strategy from [domain-strategies.md](../skills/autoresearch/references/domain-strategies.md)
   - If no built-in strategy fits, use `custom` with the user's description

Wait for user response before proceeding to Phase 2.

## Phase 2: Skill Generation

Generate a complete standalone skill in the user's project:

1. **Create the skill directory:**
   ```
   .claude/skills/autoresearch-<slug>/
   ├── SKILL.md
   ├── eval.json
   ├── scripts/
   │   ├── eval_runner.<ext>
   │   ├── loop_tracker.<ext>
   │   └── runner.py
   ├── state.json
   └── results/
   ```

2. **Generate eval.json** using the [eval-formats.md](../skills/autoresearch/references/eval-formats.md) specification:
   - Include all evals discussed during discovery
   - Set appropriate pass conditions
   - Configure target_files, protected_files, and strategy_hint
   - Set timeouts and iteration limits

3. **Generate SKILL.md** using the [skill-template.md](../skills/autoresearch/references/skill-template.md):
   - Fill in all template variables
   - Include domain-specific strategy guidance
   - Include the full loop protocol

4. **Generate scripts** in the confirmed language:
   - `eval_runner` — Uses the appropriate template from skill-template.md
   - `loop_tracker` — Uses the Python template (always Python for state management)
   - `runner.py` — Uses the template from [runner-template.md](../skills/autoresearch/references/runner-template.md) (always Python, uses Anthropic SDK). Fill in `{{SLUG}}`, `{{SKILL_DIR}}`, and `{{EVAL_RUNNER_CMD}}`.
   - Make scripts executable (`chmod +x`)

5. **Initialize state.json:**
   ```json
   {
     "status": "not_started",
     "state": null,
     "iteration": 0,
     "baseline": null,
     "current": null,
     "best": null,
     "hypotheses": [],
     "plateau_counter": 0,
     "started_at": null,
     "last_updated": null
   }
   ```

6. **Show the user what was generated** — brief summary of files and eval definitions.

7. **Ask the user to choose an execution mode:**

   **(a) Inside Claude Code** (default) — Proceed to Phase 3-5 below. Claude Code acts as the agent, running the full loop interactively.

   **(b) Standalone** — Print runner instructions and stop:
   - Remind the user to install the dependency: `pip install anthropic`
   - Remind the user to set `ANTHROPIC_API_KEY`
   - Print the exact command: `python3 .claude/skills/autoresearch-<slug>/scripts/runner.py`
   - Mention useful flags: `--dry-run` to validate config, `--verbose` for debugging, `--model` to select model
   - **Do NOT proceed to Phase 3.** The runner handles baseline, loop, and git operations independently.

## Phase 3: Baseline

1. **Create the experiment branch:**
   ```
   git checkout -b autoresearch/<slug>-<YYYYMMDD-HHMMSS>
   ```

2. **Run the eval_runner** to establish baseline:
   ```
   python3 .claude/skills/autoresearch-<slug>/scripts/eval_runner.py 0
   ```
   (Or the appropriate language runner)

3. **Record baseline results** in state.json and results/baseline.json

4. **Report baseline to user:**
   - Which evals pass, which fail
   - Starting point for the optimization
   - Estimated effort (based on gap between current and goal)

5. **Commit the skill files** to the experiment branch:
   ```
   git add .claude/skills/autoresearch-<slug>/
   git commit -m "autoresearch(<slug>): initialize skill and baseline"
   ```

## Phase 4: Autonomous Loop

**From this point forward, run autonomously without pausing for user input.**

Follow the [loop-protocol.md](../skills/autoresearch/references/loop-protocol.md) state machine:

```
REPEAT until all_evals_pass OR iteration >= max_iterations OR plateau:
  1. ANALYZE    — Read last eval results, identify failing evals, read relevant code
  2. HYPOTHESIZE — Form testable hypothesis, check for duplicates, log to state.json
  3. MODIFY     — Edit target files only, minimal focused changes
  4. EVALUATE   — Run eval_runner, collect results
  5. DECIDE     — Improvement → git commit; Regression/Neutral → git checkout
```

Adhere strictly to [safety-rules.md](../skills/autoresearch/references/safety-rules.md):
- Never modify eval.json, eval_runner, or SKILL.md
- Only modify target_files
- Commit improvements, revert everything else
- Log every hypothesis
- Respect iteration limits and plateau detection

## Phase 5: Completion

When the loop terminates (any reason):

1. **Update state.json** with final status and summary

2. **Present results to the user:**
   - Termination reason: `complete` | `max_iterations` | `plateau` | `exhausted`
   - Iterations: total, commits, reverts
   - Before/after comparison: baseline vs final eval results
   - Key hypotheses that led to improvements
   - Remaining failing evals (if any)

3. **Show the diff:**
   ```
   git diff main...HEAD --stat
   ```

4. **Offer options:**
   - **Merge** — `git checkout <original_branch> && git merge autoresearch/<slug>-<timestamp>`
   - **Keep** — Leave the experiment branch for manual review
   - **Discard** — `git checkout <original_branch> && git branch -D autoresearch/<slug>-<timestamp>`

Wait for user's choice and execute it.
