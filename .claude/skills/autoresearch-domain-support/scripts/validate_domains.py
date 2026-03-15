#!/usr/bin/env python3
"""Domain support validator for autoresearch skill.

Validates that domain strategies, templates, and eval coverage
are complete and consistent across all autoresearch reference files.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Navigate from script location to project root
# Script is at: .claude/skills/autoresearch-domain-support/scripts/validate_domains.py
# Project root is 4 levels up
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = SKILL_DIR.parent.parent.parent

DOMAIN_STRATEGIES = PROJECT_ROOT / "skills" / "autoresearch" / "references" / "domain-strategies.md"
EVAL_FORMATS = PROJECT_ROOT / "skills" / "autoresearch" / "references" / "eval-formats.md"
SKILL_TEMPLATE = PROJECT_ROOT / "skills" / "autoresearch" / "references" / "skill-template.md"
MAIN_SKILL = PROJECT_ROOT / "skills" / "autoresearch" / "SKILL.md"
AUTORESEARCH_CMD = PROJECT_ROOT / "commands" / "autoresearch.md"
EVALS_JSON = PROJECT_ROOT / "evals" / "evals.json"

REQUIRED_STRATEGIES = [
    "coverage-improvement",
    "performance-optimization",
    "test-hardening",
    "code-quality",
    "feature-completion",
    "custom",
]

REQUIRED_STRATEGY_SECTIONS = [
    "Goal",
    "Analysis approach",
    "Hypothesis patterns",
    "Common pitfalls",
]

PASS_CONDITION_TYPES = [
    "exit_code_zero",
    "output_contains",
    "output_not_contains",
    "regex_match",
    "llm_judge",
]


def extract_strategy_section(content, strategy):
    """Extract the text of a single strategy section from domain-strategies.md."""
    pattern = rf"## Strategy: `{re.escape(strategy)}`(.*?)(?=## Strategy:|## Cross-Strategy|$)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else None


def count_list_items(section_text, heading):
    """Count bullet list items under a bold heading within a section."""
    pattern = rf"\*\*{re.escape(heading)}:?\*\*:?(.*?)(?=\*\*[A-Z]|\Z)"
    match = re.search(pattern, section_text, re.DOTALL)
    if not match:
        return 0
    block = match.group(1)
    return len([l for l in block.strip().split("\n") if l.strip().startswith("-")])


def check_completeness():
    """All 6 strategies have required sections (Goal, Analysis approach, Hypothesis patterns, Common pitfalls)."""
    content = DOMAIN_STRATEGIES.read_text()
    errors = []

    for strategy in REQUIRED_STRATEGIES:
        if f"`{strategy}`" not in content:
            errors.append(f"Missing strategy: {strategy}")
            continue

        section = extract_strategy_section(content, strategy)
        if not section:
            errors.append(f"Cannot parse section for strategy: {strategy}")
            continue

        for req in REQUIRED_STRATEGY_SECTIONS:
            # Check for **Section:** or **Section** pattern
            if f"**{req}:**" not in section and f"**{req}**" not in section:
                errors.append(f"Strategy '{strategy}' missing section: {req}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    print(f"PASS: All {len(REQUIRED_STRATEGIES)} strategies have required sections")
    return True


def check_depth():
    """Each strategy has at least 3 hypothesis patterns and 3 common pitfalls."""
    content = DOMAIN_STRATEGIES.read_text()
    errors = []
    min_hypotheses = 3
    min_pitfalls = 3

    for strategy in REQUIRED_STRATEGIES:
        section = extract_strategy_section(content, strategy)
        if not section:
            errors.append(f"Cannot find strategy: {strategy}")
            continue

        hyp_count = count_list_items(section, "Hypothesis patterns")
        if hyp_count < min_hypotheses:
            errors.append(
                f"Strategy '{strategy}' has {hyp_count} hypothesis patterns (need {min_hypotheses})"
            )

        pit_count = count_list_items(section, "Common pitfalls")
        if pit_count < min_pitfalls:
            errors.append(
                f"Strategy '{strategy}' has {pit_count} pitfalls (need {min_pitfalls})"
            )

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    print(
        f"PASS: All strategies have sufficient depth "
        f"({min_hypotheses}+ hypotheses, {min_pitfalls}+ pitfalls)"
    )
    return True


def check_json_examples():
    """All JSON code blocks in eval-formats.md that represent concrete examples are valid JSON."""
    content = EVAL_FORMATS.read_text()
    errors = []

    json_blocks = re.findall(r"```json\n(.*?)```", content, re.DOTALL)

    if not json_blocks:
        errors.append("No JSON code blocks found in eval-formats.md")

    valid_count = 0
    for i, block in enumerate(json_blocks):
        # Skip schema/template blocks that use placeholder syntax
        if "<string:" in block or "<number:" in block or "<boolean:" in block:
            continue
        # Skip blocks with placeholder objects
        if "<pass_condition object>" in block:
            continue

        try:
            json.loads(block)
            valid_count += 1
        except json.JSONDecodeError as e:
            errors.append(f"JSON block {i + 1} is invalid: {e}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    print(f"PASS: All {valid_count} concrete JSON examples are valid")
    return True


def check_script_syntax():
    """Python, JS, and Shell template scripts pass syntax validation."""
    content = SKILL_TEMPLATE.read_text()
    errors = []

    # Extract and check Python templates
    py_blocks = re.findall(r"```python\n(.*?)```", content, re.DOTALL)
    for i, block in enumerate(py_blocks):
        cleaned = block.replace("{{SLUG}}", "test_slug")
        try:
            compile(cleaned, f"python_template_{i}", "exec")
        except SyntaxError as e:
            errors.append(f"Python template {i + 1} syntax error: {e}")

    # Extract and check JS templates
    js_blocks = re.findall(r"```javascript\n(.*?)```", content, re.DOTALL)
    for i, block in enumerate(js_blocks):
        cleaned = block.replace("{{SLUG}}", "test-slug")
        with tempfile.NamedTemporaryFile(
            suffix=".js", mode="w", delete=True
        ) as f:
            f.write(cleaned)
            f.flush()
            result = subprocess.run(
                ["node", "--check", f.name], capture_output=True, text=True
            )
            if result.returncode != 0:
                errors.append(
                    f"JS template {i + 1} syntax error: {result.stderr.strip()}"
                )

    # Extract and check Shell templates
    sh_blocks = re.findall(r"```bash\n(.*?)```", content, re.DOTALL)
    for i, block in enumerate(sh_blocks):
        cleaned = block.replace("{{SLUG}}", "test-slug")
        with tempfile.NamedTemporaryFile(
            suffix=".sh", mode="w", delete=True
        ) as f:
            f.write(cleaned)
            f.flush()
            result = subprocess.run(
                ["bash", "-n", f.name], capture_output=True, text=True
            )
            if result.returncode != 0:
                errors.append(
                    f"Shell template {i + 1} syntax error: {result.stderr.strip()}"
                )

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    total = len(py_blocks) + len(js_blocks) + len(sh_blocks)
    print(
        f"PASS: All {total} script templates pass syntax checks "
        f"(Python: {len(py_blocks)}, JS: {len(js_blocks)}, Shell: {len(sh_blocks)})"
    )
    return True


def check_eval_coverage():
    """evals.json test cases cover at least 5 of the 6 domain strategies."""
    evals_data = json.loads(EVALS_JSON.read_text())
    test_cases = evals_data.get("test_cases", [])

    strategy_keywords = {
        "coverage-improvement": ["coverage", "cover"],
        "performance-optimization": [
            "performance",
            "latency",
            "optimize",
            "response time",
            "speed",
        ],
        "test-hardening": ["edge case", "boundary", "harden", "edge-case"],
        "code-quality": ["lint", "quality", "complexity", "warning"],
        "feature-completion": ["feature", "acceptance", "implement"],
        "custom": ["custom"],
    }

    covered = set()
    for tc in test_cases:
        prompt = tc.get("prompt", "").lower()
        description = tc.get("setup", {}).get("description", "").lower()
        combined = prompt + " " + description

        for strategy, keywords in strategy_keywords.items():
            if any(kw in combined for kw in keywords):
                covered.add(strategy)

    missing = set(REQUIRED_STRATEGIES) - covered

    if len(covered) < 5:
        print(f"FAIL: Only {len(covered)}/6 strategies covered in evals.json")
        print(f"  Covered: {', '.join(sorted(covered))}")
        print(f"  Missing: {', '.join(sorted(missing))}")
        return False

    print(f"PASS: {len(covered)}/6 strategies covered in evals.json")
    if missing:
        print(f"  Note: still missing {', '.join(sorted(missing))}")
    return True


def check_cross_refs():
    """Strategy names are consistent across all reference files."""
    errors = []

    strategies_content = DOMAIN_STRATEGIES.read_text()
    skill_content = MAIN_SKILL.read_text()
    cmd_content = AUTORESEARCH_CMD.read_text()

    # Check each strategy exists in domain-strategies.md
    for strategy in REQUIRED_STRATEGIES:
        if strategy not in strategies_content:
            errors.append(f"Strategy '{strategy}' not found in domain-strategies.md")

    # Check domain-strategies.md is referenced from SKILL.md
    if (
        "domain-strategies" not in skill_content.lower()
        and "domain strategies" not in skill_content.lower()
    ):
        errors.append("SKILL.md does not reference domain strategies")

    # Check autoresearch.md references strategy selection
    if "strategy" not in cmd_content.lower():
        errors.append("autoresearch.md does not reference strategy selection")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    print("PASS: Strategy references are consistent across files")
    return True


def check_pass_conditions():
    """All 5 pass_condition types are documented with examples in eval-formats.md."""
    content = EVAL_FORMATS.read_text()
    errors = []

    for pct in PASS_CONDITION_TYPES:
        if pct not in content:
            errors.append(
                f"Pass condition type '{pct}' not documented in eval-formats.md"
            )
        # Check there's a JSON example containing this type
        if f'"type": "{pct}"' not in content:
            errors.append(
                f"Pass condition type '{pct}' lacks a JSON example in eval-formats.md"
            )

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    print(f"PASS: All {len(PASS_CONDITION_TYPES)} pass_condition types are documented with examples")
    return True


def check_actionability():
    """Each strategy provides concrete file patterns and guidance."""
    content = DOMAIN_STRATEGIES.read_text()
    errors = []

    for strategy in REQUIRED_STRATEGIES:
        section = extract_strategy_section(content, strategy)
        if not section:
            errors.append(f"Cannot find strategy: {strategy}")
            continue

        # Check for target file patterns
        if "Target file" not in section and "target_file" not in section:
            errors.append(f"Strategy '{strategy}' missing target file patterns")

        # Check for protected file patterns
        if "Protected file" not in section and "protected_file" not in section:
            errors.append(f"Strategy '{strategy}' missing protected file patterns")

        # Check for concrete glob patterns or file extensions (skip custom check for globs)
        has_pattern = bool(re.search(r"[*]{1,2}/|\.\w+|`[^`]+\.\w+`", section))
        if not has_pattern:
            errors.append(f"Strategy '{strategy}' lacks concrete file glob patterns")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return False

    print("PASS: All strategies provide actionable file patterns and guidance")
    return True


CHECKS = {
    "completeness": check_completeness,
    "depth": check_depth,
    "json-examples": check_json_examples,
    "script-syntax": check_script_syntax,
    "eval-coverage": check_eval_coverage,
    "cross-refs": check_cross_refs,
    "pass-conditions": check_pass_conditions,
    "actionability": check_actionability,
}


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <{'|'.join(CHECKS.keys())}>")
        sys.exit(1)

    check_name = sys.argv[1]
    if check_name not in CHECKS:
        print(f"Unknown check: {check_name}")
        print(f"Available: {', '.join(CHECKS.keys())}")
        sys.exit(1)

    passed = CHECKS[check_name]()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
