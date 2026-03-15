# Safety Rules

Non-negotiable guardrails for autoresearch autonomous loop execution.

## File Restrictions

### Target Files (Agent May Modify)

- Only files matching `config.target_files` glob patterns may be modified
- Verify each file against the glob before editing
- If a needed change is outside target_files, **stop and report** — do not expand scope

### Protected Files (Agent Must Not Modify)

- Files matching `config.protected_files` glob patterns are strictly off-limits
- Common protected files: `package.json`, `*.lock`, `setup.py`, `pyproject.toml`, `go.mod`, `Cargo.toml`
- **eval.json is always protected** — it defines the ground truth
- **eval_runner scripts are always protected** — they execute the ground truth
- **SKILL.md is always protected** — it defines the agent's behavior

### Implicit Protections

These files are protected even if not listed in `protected_files`:

- `.git/` — Never modify git internals
- `.env`, `.env.*` — Never modify environment files
- `**/secrets.*`, `**/credentials.*` — Never modify secret files
- CI/CD configs (`.github/`, `.gitlab-ci.yml`, `Jenkinsfile`) — Never modify CI
- The skill directory itself (`<skill_path>/**`) — except for `state.json` and `results/`

## Git Safety

### Branch Protocol

- All loop work happens on a dedicated experiment branch
- Branch name format: `autoresearch/<slug>-<YYYYMMDD-HHMMSS>`
- Never modify `main`, `master`, or the branch the user was on when starting
- The experiment branch is created from the user's current HEAD

### Commit Protocol

- Only commit when eval results show improvement
- Commit message format: `autoresearch(<slug>): iter <N> — <hypothesis summary>`
- Each commit contains only target_file changes
- Never use `--amend` — every commit is new
- Never use `--force` for any git operation

### Revert Protocol

- Revert on regression or neutral results
- Use `git checkout -- <target_files>` for clean revert
- If revert fails, stop the loop immediately — state is uncertain
- Never use `git reset --hard` — it's too broad

### Post-Loop

- Never merge the experiment branch automatically
- Never push to remote automatically
- Present options to the user: merge, keep, discard

## Execution Safety

### Timeouts

- Every eval command has a timeout (`timeout_per_eval_seconds`, default 120s)
- Every iteration has a timeout (`timeout_per_iteration_seconds`, default 600s)
- If a timeout is hit, treat the eval as failed (not as an error)
- Never increase timeouts during the loop

### Resource Limits

- Do not spawn background processes that outlive the eval
- Do not write to files outside the project directory
- Do not make network requests unless the eval command requires it
- Do not install packages or modify dependencies during the loop

### Eval Integrity

- Run evals exactly as specified in eval.json
- Do not modify eval commands to make them pass
- Do not skip failing evals
- Do not add `|| true` or similar to eval commands
- If an eval is broken (always fails regardless of code), stop and report

## Agent Behavior Rules

### No Random Changes

- Every modification must be based on a logged hypothesis
- Never make random changes hoping they improve metrics
- Never copy code from the internet without understanding it
- Never generate fake test data that makes evals pass without real improvement

### No Scope Creep

- Each iteration addresses exactly one hypothesis
- Do not refactor code "while you're there"
- Do not add features beyond what the hypothesis requires
- Do not optimize code that isn't related to failing evals

### No Gaming the Evals

The agent must not try to "trick" the eval system:

- Do not hardcode expected outputs to make regex_match pass
- Do not add `print("expected string")` to make output_contains pass
- Do not delete test cases to make tests-pass succeed
- Do not modify eval infrastructure to change pass/fail thresholds
- Do not write code that behaves differently under eval vs production conditions

### Honest Reporting

- Report actual results, not desired results
- If the loop fails to achieve the goal, say so
- If a hypothesis was wrong, log it as wrong
- If the agent is stuck, report it rather than thrashing

### No Interactive Prompts

- During the autonomous loop, never prompt the user for input
- If human decision is needed, stop the loop and report why
- The loop must be fully autonomous from start to DONE

## Escalation Protocol

Stop the loop and report to the user if:

1. **Eval infrastructure is broken** — Commands can't run, dependencies missing
2. **Git state is uncertain** — Revert failed, merge conflict, detached HEAD
3. **All hypotheses exhausted** — Can't form a new viable approach
4. **Security concern** — Eval requires network access, privilege escalation, or file access outside project
5. **Unexpected state** — Files modified outside target_files, eval results are inconsistent
6. **Resource limit** — Disk space, memory, or CPU concerns

When stopping, always:
1. Save current state to `state.json` with status `interrupted`
2. Revert any uncommitted changes
3. Report what happened and why the loop stopped
4. Suggest next steps for the user
