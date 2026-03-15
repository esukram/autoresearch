#!/usr/bin/env python3
"""Loop state tracker for autoresearch-domain-support. Manages the optimization loop state machine."""

import json
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
STATE_FILE = SKILL_DIR / "state.json"

VALID_STATES = ("init", "analyze", "hypothesize", "modify", "evaluate", "decide", "done")

TRANSITIONS = {
    "init": {"analyze"},
    "analyze": {"hypothesize", "done"},
    "hypothesize": {"modify"},
    "modify": {"evaluate"},
    "evaluate": {"decide"},
    "decide": {"analyze", "done"},
    "done": set(),
    None: {"init"},
}


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


def cmd_status(state):
    print(f"Status:    {state['status']}")
    print(f"State:     {state['state'] or 'not started'}")
    print(f"Iteration: {state['iteration']}")
    if state["current"]:
        print(f"Passing:   {state['current']['pass_count']}/{state['current']['total']}")
    if state["best"]:
        print(f"Best:      {state['best']['pass_count']}/{state['best']['total']} (iter {state['best']['iteration']})")
    print(f"Plateau:   {state['plateau_counter']}")
    print(f"Hypotheses tried: {len(state['hypotheses'])}")


def cmd_transition(state, target):
    if target not in VALID_STATES:
        print(f"ERROR: Invalid state '{target}'. Must be one of: {', '.join(VALID_STATES)}")
        sys.exit(1)

    current = state["state"]
    allowed = TRANSITIONS.get(current, {"init"})

    if target not in allowed:
        print(f"WARNING: Transition {current or 'none'} -> {target} is not standard.")
        print(f"  Expected: {', '.join(sorted(allowed))}")

    state["state"] = target
    if target == "init":
        state["status"] = "running"
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    elif target == "done":
        state["status"] = state.get("done_reason", "complete")
        state["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    elif target == "analyze":
        state["iteration"] += 1

    save_state(state)
    print(f"[{target.upper()}] iteration {state['iteration']}")
    return state


def cmd_hypothesis(state, hypothesis, target_eval, target_files):
    entry = {
        "iteration": state["iteration"],
        "hypothesis": hypothesis,
        "target_eval": target_eval,
        "target_files": target_files,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "result": None,
    }
    state["hypotheses"].append(entry)
    save_state(state)
    print(f"Logged hypothesis for iteration {state['iteration']}: {hypothesis[:80]}")


def cmd_result(state, pass_count, fail_count, total, committed):
    state["current"] = {"pass_count": pass_count, "fail_count": fail_count, "total": total}

    if committed:
        state["plateau_counter"] = 0
        if not state["best"] or pass_count > state["best"]["pass_count"]:
            state["best"] = {**state["current"], "iteration": state["iteration"]}
        if state["hypotheses"]:
            state["hypotheses"][-1]["result"] = "committed"
    else:
        state["plateau_counter"] += 1
        if state["hypotheses"]:
            state["hypotheses"][-1]["result"] = "reverted"

    save_state(state)
    status = "COMMIT" if committed else "REVERT"
    print(f"[{status}] {pass_count}/{total} passing (plateau: {state['plateau_counter']})")


def cmd_reset():
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print("State reset.")
    else:
        print("No state file found.")


def main():
    if len(sys.argv) < 2:
        print("Usage: loop_tracker.py <status|transition|hypothesis|result|reset> [args]")
        sys.exit(1)

    command = sys.argv[1]
    state = load_state()

    if command == "status":
        cmd_status(state)
    elif command == "transition":
        if len(sys.argv) < 3:
            print("ERROR: transition requires a state argument")
            sys.exit(1)
        cmd_transition(state, sys.argv[2])
    elif command == "hypothesis":
        if len(sys.argv) < 5:
            print("ERROR: hypothesis requires: <text> <target_eval> <target_files>")
            sys.exit(1)
        cmd_hypothesis(state, sys.argv[2], sys.argv[3], sys.argv[4].split(","))
    elif command == "result":
        if len(sys.argv) < 6:
            print("ERROR: result requires: <pass_count> <fail_count> <total> <committed:true|false>")
            sys.exit(1)
        cmd_result(state, int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5] == "true")
    elif command == "reset":
        cmd_reset()
    else:
        print(f"ERROR: Unknown command '{command}'")
        sys.exit(1)


if __name__ == "__main__":
    main()
