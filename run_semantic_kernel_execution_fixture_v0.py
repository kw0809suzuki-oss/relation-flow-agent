#!/usr/bin/env python3
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import semantic_kernel_wheat3_execution_fixture_v0 as candidate


OPPONENT = base.OPPONENT
SEED = 4142
SEAT = 0


def configure(agent_module):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.reset_telemetry()
    if hasattr(agent_module, "reset_telemetry"):
        agent_module.reset_telemetry()


def play(agent_module):
    configure(agent_module)
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    actions = []

    def observed(obs):
        action = agent_module.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(state.reward) for state in env.state]

    out = {
        "actions": actions,
        "rewards": rewards,
    }
    if hasattr(agent_module, "get_trace"):
        trace = agent_module.get_trace()
        if isinstance(trace, dict) and "semantic_execution" in trace:
            out["semantic_execution"] = trace["semantic_execution"]
    return out


def first_difference(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    return None


def main():
    b = play(baseline)
    c = play(candidate)

    trace = c.get("semantic_execution", [])
    applied = [
        row for row in trace
        if any(item.get("status") == "applied" for item in row.get("execution", []))
    ]
    target_row = next((row for row in trace if row.get("turn") == 108), None)

    result = {
        "schema": "kaggriculture.semantic-kernel-execution-fixture.v0",
        "seed": SEED,
        "seat": SEAT,
        "fixture": "Turn108 suppress BUY_SEED WHEAT 3",
        "checks": {
            "trace_complete": len(trace) == len(c["actions"]),
            "turn108_present": target_row is not None,
            "turn108_rule_eligible": bool(target_row and "SUPPRESS_WHEAT3_T108" in target_row.get("eligible_rule_ids", [])),
            "turn108_rule_selected": bool(target_row and "SUPPRESS_WHEAT3_T108" in target_row.get("selected_rule_ids", [])),
            "turn108_plan_valid": bool(target_row and target_row.get("plan_status") == "valid"),
            "execution_applied_once": len(applied) == 1,
            "first_action_difference_is_108": first_difference(c["actions"], b["actions"]) == 108,
        },
        "counts": {
            "baseline_actions": len(b["actions"]),
            "candidate_actions": len(c["actions"]),
            "trace_rows": len(trace),
            "applied_count": len(applied),
        },
        "terminal": {
            "baseline_rewards": b["rewards"],
            "candidate_rewards": c["rewards"],
            "self_diff": c["rewards"][SEAT] - b["rewards"][SEAT],
            "margin_diff": (c["rewards"][SEAT] - c["rewards"][1-SEAT]) - (b["rewards"][SEAT] - b["rewards"][1-SEAT]),
        },
        "turn108": target_row,
    }
    result["pass"] = all(result["checks"].values())

    Path("semantic_kernel_execution_fixture_v0_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print("SEMANTIC_KERNEL_EXECUTION_FIXTURE " + json.dumps({
        "checks": result["checks"],
        "terminal": result["terminal"],
    }, separators=(",", ":")))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
