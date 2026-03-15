# Autonomous Loop Protocol

This document defines the state machine and step-by-step protocol for the autoresearch autonomous optimization loop.

## State Machine

```
INIT ──► ANALYZE ──► HYPOTHESIZE ──► MODIFY ──► EVALUATE ──► DECIDE ──┐
                 ▲                                                     │
                 │               (improvement: commit)                 │
                 └─────────────────────────────────────────────────────┘
                                                                       │
                                 (all pass OR max_iter OR plateau)      │
                                                                       ▼
                                                                     DONE
```

### States

| State | Description |
|-------|-------------|
| `INIT` | Load eval.json, validate config, run baseline, create branch |
| `ANALYZE` | Read last eval results, identify failing evals, determine priority |
| `HYPOTHESIZE` | Form a testable hypothesis about what change will fix a failing eval |
| `MODIFY` | Implement the hypothesized change in target files only |
| `EVALUATE` | Run all evals via eval_runner, collect pass/fail results |
| `DECIDE` | Compare results to previous iteration; commit or revert |
| `DONE` | Summarize results, present options to user |

### Transitions

- `INIT → ANALYZE` — After baseline is recorded
- `ANALYZE → HYPOTHESIZE` — After identifying which evals to target
- `HYPOTHESIZE → MODIFY` — After logging the hypothesis
- `MODIFY → EVALUATE` — After code changes are complete
- `EVALUATE → DECIDE` — After eval results are collected
- `DECIDE → ANALYZE` — After commit/revert, if loop should continue
- `DECIDE → DONE` — If all evals pass, max iterations reached, or plateau detected

## Detailed Protocol

### Step 0: INIT

1. Load `eval.json` from the generated skill directory
2. Validate all fields: version, evals array, config
3. Verify target files exist (or glob patterns match at least one file)
4. Verify eval commands can execute (dry run with timeout)
5. Create experiment branch: `autoresearch/<slug>-<YYYYMMDD-HHMMSS>`
6. Run all evals to establish baseline
7. Write `results/baseline.json` with full eval results
8. Initialize `state.json`:

```json
{
  "status": "running",
  "iteration": 0,
  "baseline": { "pass_count": 2, "fail_count": 3, "total": 5 },
  "current": { "pass_count": 2, "fail_count": 3, "total": 5 },
  "best": { "pass_count": 2, "fail_count": 3, "total": 5, "iteration": 0 },
  "hypotheses": [],
  "plateau_counter": 0,
  "started_at": "<ISO timestamp>",
  "last_updated": "<ISO timestamp>"
}
```

9. Transition to ANALYZE

### Step 1: ANALYZE

1. Read the latest eval results (baseline or last iteration)
2. Identify all failing evals, sorted by:
   - `required` evals first
   - Evals closest to passing (highest partial progress)
   - Evals with the most information in failure output
3. Select the **primary target eval** — the one most likely to be fixable in one iteration
4. Read the target files relevant to this eval
5. Read any error output, stack traces, or failure messages
6. Summarize the current state:
   - Which evals pass, which fail
   - What the failure modes are
   - What has been tried before (from hypothesis log)

### Step 2: HYPOTHESIZE

1. Based on the analysis, form a **specific, testable hypothesis**:
   - "Adding input validation to `parse_request()` will fix the `input-validation` eval"
   - "Extracting the retry logic into a helper will reduce the timeout in `api-latency` eval"
2. Check the hypothesis log for repetition:
   - Has this exact hypothesis been tried before?
   - Has a similar approach been tried and failed?
   - If repeating, form a **different** hypothesis
3. Log the hypothesis to state.json:

```json
{
  "iteration": 5,
  "hypothesis": "Adding boundary check to parse_int() will fix the overflow eval",
  "target_eval": "integer-overflow",
  "target_files": ["src/parser.py"],
  "timestamp": "<ISO timestamp>"
}
```

4. If no viable hypothesis exists (all approaches exhausted), transition to DONE with status `exhausted`

### Step 3: MODIFY

1. **Pre-flight checks:**
   - Confirm all files to modify are within `target_files` globs
   - Confirm no files are in `protected_files` globs
   - If a file is outside bounds, revise the hypothesis
2. **Make the changes:**
   - Edit target files to implement the hypothesis
   - Keep changes minimal and focused on the hypothesis
   - Do not refactor unrelated code
   - Do not add features beyond what the hypothesis requires
3. **Post-modification:**
   - Verify the changes compile/parse (syntax check)
   - If syntax errors, fix them before proceeding to EVALUATE

### Step 4: EVALUATE

1. Run the eval_runner script (or execute eval commands directly)
2. For each eval in eval.json:
   - Execute the command with the configured timeout
   - Capture stdout, stderr, and exit code
   - Apply the pass_condition to determine pass/fail
   - For `regex_match`: extract the captured group and compare against threshold
   - For `llm_judge`: evaluate the output against the criteria (agent handles inline)
3. Collect results into an iteration result:

```json
{
  "iteration": 5,
  "timestamp": "<ISO timestamp>",
  "hypothesis": "<from step 2>",
  "results": [
    {
      "eval_id": "tests-pass",
      "passed": true,
      "output_summary": "42 passed, 0 failed",
      "duration_seconds": 3.2
    },
    {
      "eval_id": "coverage-target",
      "passed": false,
      "output_summary": "Coverage: 72% (target: 80%)",
      "extracted_value": 72,
      "duration_seconds": 5.1
    }
  ],
  "pass_count": 3,
  "fail_count": 2,
  "total": 5
}
```

4. Write results to `results/iter-<NNN>.json`

### Step 5: DECIDE

Compare the current iteration results to the **previous committed state** (not baseline):

**Improvement detected** (pass_count increased OR a required eval flipped from fail to pass):
1. Stage and commit the changes: `git add <target_files> && git commit -m "autoresearch: iter <N> — <hypothesis summary>"`
2. Update state.json: increment `current.pass_count`, reset `plateau_counter`
3. Update `best` if this is the best result so far
4. Log: `COMMIT — iteration <N>: <pass_count>/<total> evals passing (+<delta>)`

**Regression detected** (pass_count decreased OR a required eval flipped from pass to fail):
1. Revert all changes: `git checkout -- <target_files>`
2. Keep `plateau_counter` as-is (a regression is not a plateau)
3. Log: `REVERT — iteration <N>: regression detected (<details>)`

**Neutral** (same pass_count, no required eval changes):
1. Revert all changes: `git checkout -- <target_files>`
2. Increment `plateau_counter`
3. Log: `REVERT — iteration <N>: no improvement`

**Termination check:**
- If `pass_count == total`: transition to DONE with status `complete`
- If `iteration >= max_iterations`: transition to DONE with status `max_iterations`
- If `plateau_counter >= plateau_threshold`: transition to DONE with status `plateau`
- Otherwise: transition to ANALYZE

### Step 6: DONE

1. Update state.json with final status:

```json
{
  "status": "complete|max_iterations|plateau|exhausted|interrupted",
  "completed_at": "<ISO timestamp>",
  "summary": {
    "total_iterations": 23,
    "commits": 12,
    "reverts": 11,
    "baseline_pass_count": 2,
    "final_pass_count": 5,
    "improvement": "+3 evals passing"
  }
}
```

2. Present results to the user:
   - Summary of iterations, commits, reverts
   - Before/after eval comparison
   - Key hypotheses that led to improvements
   - Remaining failing evals (if any)
3. Offer options:
   - **Merge** — Merge the experiment branch into the current branch
   - **Keep** — Leave the experiment branch for manual review
   - **Discard** — Delete the experiment branch

## Plateau Detection

A plateau occurs when the loop makes no progress for `plateau_threshold` consecutive iterations. This indicates the agent has exhausted its current strategies.

**What counts as a plateau increment:**
- Neutral result (same pass_count, reverted)

**What resets the plateau counter:**
- Any improvement (pass_count increases)

**What does NOT affect the plateau counter:**
- Regressions (these are different from stagnation)

## Hypothesis Deduplication

The agent must avoid repeating failed hypotheses. Before forming a new hypothesis:

1. Check `state.json` hypotheses array for previous attempts
2. If the same hypothesis was tried and resulted in a revert, try a **different approach**
3. If all obvious approaches have been tried for a failing eval, move to a different eval
4. If all evals have been attempted without progress, report `exhausted`

Similarity heuristic: two hypotheses are "the same" if they target the same file, same function, and same type of change. The agent should vary at least one dimension.

## Error Handling During Loop

**Eval command timeout:**
- Treat as a failing eval (not an error)
- Log the timeout in results
- Continue the loop

**Eval command crashes (non-zero exit that isn't eval failure):**
- Distinguish between "test failed" (expected) and "couldn't run tests" (infrastructure)
- If infrastructure failure: attempt to fix (e.g., missing import), then re-evaluate
- If repeated infrastructure failures: stop the loop, report the issue

**Git operations fail:**
- If commit fails: retry once, then stop the loop
- If revert fails: stop the loop immediately (state is uncertain)

**Agent uncertainty:**
- If the agent cannot form a hypothesis, stop with status `exhausted`
- Never make random changes hoping they work
