---
name: autoresearch-init
description: Initialize an autoresearch skill for a domain without starting the loop
argument-hint: "<domain>"
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# /autoresearch-init

Generate an autoresearch skill without running the optimization loop. This allows the user to review and customize the skill before running it.

Follow Phase 1 (Discovery) and Phase 2 (Skill Generation) from the [/autoresearch command](autoresearch.md), then stop.

## Steps

1. **Discovery** — Parse `$ARGUMENTS`, detect stack, ask clarifying questions (same as /autoresearch Phase 1)

2. **Skill Generation** — Generate the complete skill directory (same as /autoresearch Phase 2):
   ```
   .claude/skills/autoresearch-<slug>/
   ├── SKILL.md
   ├── eval.json
   ├── scripts/
   │   ├── eval_runner.<ext>
   │   └── loop_tracker.<ext>
   ├── state.json
   └── results/
   ```

3. **Do NOT create an experiment branch or run the baseline.**

4. **Present the generated skill for review:**
   - Show the eval.json contents
   - Summarize the SKILL.md
   - List all generated files
   - Explain what each eval checks and what the pass conditions are

5. **Tell the user how to proceed:**
   - Review and edit eval.json if needed (adjust thresholds, add/remove evals)
   - Review target_files and protected_files
   - When ready, run `/autoresearch-resume` to start the loop
   - Or run `/autoresearch "<same goal>"` to regenerate from scratch
