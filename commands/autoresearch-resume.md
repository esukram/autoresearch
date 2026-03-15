---
name: autoresearch-resume
description: Resume an interrupted autoresearch loop from its last checkpoint
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, Agent
---

# /autoresearch-resume

Resume an interrupted autoresearch loop from its last saved state.

## Steps

1. **Find autoresearch skills** in the project:
   ```
   ls -d .claude/skills/autoresearch-*/ 2>/dev/null
   ```

2. If multiple skills exist, list them with their status and ask the user which one to resume.

3. **Load state.json** for the selected skill:
   - If status is `not_started`: run baseline (Phase 3) then start the loop (Phase 4)
   - If status is `running` or `interrupted`: resume from the saved state
   - If status is `complete`, `max_iterations`, `plateau`, or `exhausted`: report that the loop has already finished and show results

4. **Verify the experiment branch exists:**
   ```
   git branch --list 'autoresearch/<slug>-*'
   ```
   - If the branch exists, check it out
   - If not, create a new one from the current HEAD

5. **Verify state consistency:**
   - Check that eval.json still exists and is valid
   - Check that scripts exist and are executable
   - Check that target files still match the glob patterns
   - If anything is missing, report and stop

6. **Resume the loop from the current state:**

   Based on `state.state` in state.json:
   - `init` → Run baseline, then start the loop
   - `analyze` → Start a new iteration from ANALYZE
   - `hypothesize` → Re-analyze (the previous hypothesis wasn't applied)
   - `modify` → Revert uncommitted changes, re-analyze
   - `evaluate` → Revert uncommitted changes, re-analyze
   - `decide` → Revert uncommitted changes, re-analyze
   - `done` → Show results (loop already finished)

   For any state with uncommitted changes, revert first:
   ```
   git checkout -- <target_files>
   ```

7. **Continue with the autonomous loop** (Phase 4 from /autoresearch) using the existing skill, eval.json, and state.

8. **On completion**, follow Phase 5 from /autoresearch (present results, offer merge/keep/discard).
