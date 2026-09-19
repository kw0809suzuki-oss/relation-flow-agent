#!/usr/bin/env python3
"""One-battle shadow integration check for Semantic Kernel v2.

The shadow path must not alter gameplay. It only observes the production obs,
runs semantic evaluation, records the trace, and returns the unchanged native action.
"""

import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import whole_flow_control_agent as baseline_agent
import semantic_kernel_shadow_agent_v0 as shadow_agent


OPPONENT = "opponents/seyamalam_v21.py"
SEED = 3202
SEAT = 0


def configure(agent_module):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    agent_module.set_control_enabled(False)
    agent_module.set_probe_enabled(True)
    agent_module.set_attribution_enabled(True)
    agent_module.reset_telemetry()


def play(agent_module, shadow=False):
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
    rewards = [state.reward for state in env.state]
    result = {
        "actions": actions,
        "rewards": rewards,
    }
    if shadow:
        result["semantic_trace"] = agent_module.get_trace()["semantic_shadow"]
    return result


def main():
    baseline = play(baseline_agent, shadow=False)
    shadow = play(shadow_agent, shadow=True)

    actions_equal = baseline["actions"] == shadow["actions"]
    rewards_equal = baseline["rewards"] == shadow["rewards"]
    trace = shadow["semantic_trace"]
    trace_complete = len(trace) == len(shadow["actions"])
    emitted_match = all(
        row.get("emitted_action") == action
        for row, action in zip(trace, shadow["actions"])
    )

    result = {
        "schema": "kaggriculture.semantic-kernel-shadow-integration.v0",
        "seed": SEED,
        "seat": SEAT,
        "mode": "shadow-only",
        "baseline_control_enabled": False,
        "semantic_kernel_changes_gameplay": False,
        "checks": {
            "actions_equal": actions_equal,
            "rewards_equal": rewards_equal,
            "trace_complete": trace_complete,
            "emitted_action_matches_trace": emitted_match,
        },
        "counts": {
            "actions": len(shadow["actions"]),
            "semantic_trace_rows": len(trace),
            "eligible_nonempty": sum(bool(row.get("eligible_rule_ids")) for row in trace),
            "selected_nonempty": sum(bool(row.get("selected_rule_ids")) for row in trace),
            "plan_valid": sum(row.get("plan_status") == "valid" for row in trace),
            "plan_invalid": sum(row.get("plan_status") == "invalid" for row in trace),
        },
        "terminal": {
            "baseline_rewards": baseline["rewards"],
            "shadow_rewards": shadow["rewards"],
        },
        "sample_trace": trace[:5],
        "pass": actions_equal and rewards_equal and trace_complete and emitted_match,
    }

    Path("semantic_kernel_shadow_integration_v0_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print("SEMANTIC_KERNEL_SHADOW_INTEGRATION " + json.dumps(result["checks"], separators=(",", ":")))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
