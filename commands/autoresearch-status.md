---
name: autoresearch-status
description: Check progress of a running or completed autoresearch loop
arguments: []
---

# /autoresearch-status

Check the status of autoresearch optimization loops in this project.

## Steps

1. **Find all autoresearch skills** in the project:
   ```
   ls -d .claude/skills/autoresearch-*/ 2>/dev/null
   ```

2. If no skills found, report: "No autoresearch skills found in this project. Use `/autoresearch \"<goal>\"` to start one."

3. For each skill found, **read state.json**:
   ```
   cat .claude/skills/autoresearch-<slug>/state.json
   ```

4. **Present a status summary** for each skill:

   ```
   ## autoresearch-<slug>
   Status:     <running | complete | max_iterations | plateau | exhausted | interrupted | not_started>
   Goal:       <from eval.json>
   Iteration:  <current> / <max>
   Passing:    <pass_count> / <total> evals
   Best:       <best_pass_count> / <total> (iteration <N>)
   Plateau:    <counter> / <threshold>
   Started:    <timestamp>
   Last update: <timestamp>
   ```

5. If the status is `running`, also show:
   - Current state in the loop (ANALYZE, HYPOTHESIZE, MODIFY, EVALUATE, DECIDE)
   - Last hypothesis tried
   - Last eval results

6. If the status is a terminal state (`complete`, `max_iterations`, `plateau`, `exhausted`), also show:
   - Total commits and reverts
   - Baseline vs final comparison
   - Experiment branch name

7. **Check for experiment branches:**
   ```
   git branch --list 'autoresearch/*'
   ```
   Report any branches and whether they've been merged.
