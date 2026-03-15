#!/usr/bin/env python3
"""Eval runner for autoresearch-domain-support. DO NOT MODIFY during loop."""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
EVAL_CONFIG = SKILL_DIR / "eval.json"
RESULTS_DIR = SKILL_DIR / "results"


def load_config():
    return json.loads(EVAL_CONFIG.read_text())


def run_eval(eval_def, timeout):
    start = time.time()
    try:
        result = subprocess.run(
            eval_def["command"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.time() - start
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": round(duration, 2),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout}s",
            "duration_seconds": round(duration, 2),
            "timed_out": True,
        }


def check_pass_condition(condition, run_result):
    ctype = condition["type"]
    output = run_result["stdout"] + run_result["stderr"]

    if ctype == "exit_code_zero":
        return run_result["exit_code"] == 0

    if ctype == "output_contains":
        return condition["value"] in output

    if ctype == "output_not_contains":
        return condition["value"] not in output

    if ctype == "regex_match":
        match = re.search(condition["pattern"], output)
        if not match:
            return False
        try:
            value = float(match.group(condition.get("group", 1)))
        except (IndexError, ValueError):
            return False
        threshold = condition["threshold"]
        op = condition["operator"]
        if op == ">=": return value >= threshold
        if op == ">":  return value > threshold
        if op == "<=": return value <= threshold
        if op == "<":  return value < threshold
        if op == "==": return value == threshold
        if op == "!=": return value != threshold
        return False

    if ctype == "llm_judge":
        print(f"LLM_JUDGE_EVAL:{json.dumps({'output': output, 'criteria': condition['criteria']})}")
        return None

    return False


def main():
    config = load_config()
    default_timeout = config["config"].get("timeout_per_eval_seconds", 120)
    RESULTS_DIR.mkdir(exist_ok=True)

    iteration = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    results = []
    pass_count = 0
    fail_count = 0

    for eval_def in config["evals"]:
        timeout = eval_def.get("timeout_seconds", default_timeout)
        run_result = run_eval(eval_def, timeout)
        passed = check_pass_condition(eval_def["pass_condition"], run_result)

        result_entry = {
            "eval_id": eval_def["id"],
            "passed": passed,
            "output_summary": (run_result["stdout"] + run_result["stderr"])[:500],
            "duration_seconds": run_result["duration_seconds"],
            "timed_out": run_result["timed_out"],
        }

        if eval_def["pass_condition"]["type"] == "regex_match":
            output = run_result["stdout"] + run_result["stderr"]
            match = re.search(eval_def["pass_condition"]["pattern"], output)
            if match:
                try:
                    result_entry["extracted_value"] = float(
                        match.group(eval_def["pass_condition"].get("group", 1))
                    )
                except (IndexError, ValueError):
                    pass

        results.append(result_entry)
        if passed:
            pass_count += 1
        elif passed is not None:
            fail_count += 1

    output = {
        "iteration": iteration,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total": len(config["evals"]),
    }

    if iteration == 0:
        result_file = RESULTS_DIR / "baseline.json"
    else:
        result_file = RESULTS_DIR / f"iter-{iteration:03d}.json"
    result_file.write_text(json.dumps(output, indent=2) + "\n")

    print(f"Evals: {pass_count}/{len(config['evals'])} passing")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['eval_id']} ({r['duration_seconds']}s)")

    sys.exit(0 if pass_count == len(config["evals"]) else 1)


if __name__ == "__main__":
    main()
