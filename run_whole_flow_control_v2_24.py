#!/usr/bin/env python3
"""24-case expansion for the unchanged V2 vector-majority Relation Flow controller."""

import copy
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
CASES = (
    (3202, 0), (3206, 0), (3215, 1), (3218, 0),
    (3222, 0), (3227, 1), (3231, 1), (3240, 0),
    (3243, 1), (3246, 0), (3250, 0), (3251, 1),
    (3252, 0), (3253, 1), (3254, 0), (3255, 1),
    (3256, 0), (3257, 1), (3258, 0), (3259, 1),
    (3260, 0), (3261, 1), (3262, 0), (3263, 1),
)


def configure(enabled):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    agent.set_control_enabled(enabled)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def score(rewards, seat):
    own = float(rewards[seat])
    opponent = float(rewards[1 - seat])
    return {"self": own, "opponent": opponent, "margin": own - opponent, "win": own > opponent}


def play(seed, seat, enabled):
    configure(enabled)
    actions = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        action = agent.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {
        "score": score(rewards, seat),
        "actions": actions,
        "telemetry": agent.get_telemetry(),
        "flow_trace": agent.get_trace()["whole_flow"],
    }


def first_difference(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return None


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, False)
        candidate = play(seed, seat, True)
        delta = {
            key: candidate["score"][key] - baseline["score"][key]
            for key in ("self", "opponent", "margin")
        }
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": baseline["score"],
            "candidate": candidate["score"],
            "terminal_delta": delta,
            "direction": "improved" if delta["margin"] > 0 else "worsened" if delta["margin"] < 0 else "equal",
            "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
            "action_difference_count": sum(a != b for a, b in zip(candidate["actions"], baseline["actions"])),
            "control_telemetry": candidate["telemetry"],
            "flow_trace": candidate["flow_trace"],
        })

    directions = Counter(row["direction"] for row in rows)
    deltas = [row["terminal_delta"]["margin"] for row in rows]
    old_deltas = deltas[:12]
    new_deltas = deltas[12:]
    summary = {
        "case_count": len(rows),
        "mean_margin_delta": sum(deltas) / len(deltas),
        "existing12_mean_margin_delta": sum(old_deltas) / len(old_deltas),
        "added12_mean_margin_delta": sum(new_deltas) / len(new_deltas),
        "baseline_wins": sum(row["baseline"]["win"] for row in rows),
        "candidate_wins": sum(row["candidate"]["win"] for row in rows),
        "direction_counts": dict(directions),
        "worsened_seed_count": directions.get("worsened", 0),
        "largest_worsening": min(deltas),
        "largest_improvement": max(deltas),
        "action_difference_cases": sum(row["first_action_difference"] is not None for row in rows),
        "total_action_differences": sum(row["action_difference_count"] for row in rows),
    }
    summary["win_delta"] = summary["candidate_wins"] - summary["baseline_wins"]

    result = {
        "schema": "kaggriculture.whole-relation-flow-control.v2-vector-majority.expansion24",
        "question": "does the unchanged V2 vector-majority Relation Flow effect survive expansion from 12 to 24 predeclared cases?",
        "design_unit": "unchanged V2 controller; only case count expanded",
        "relation_axes": ["money", "capacity", "public_production"],
        "flow_horizon": "V1-compatible history implementation: initial 24-call comparison, then effective 25-call gap",
        "modes": MODE_DESCRIPTION,
        "cases": rows,
        "summary": summary,
        "added_cases": list(CASES[12:]),
        "runtime_inputs_excluded": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "native_origin_direction_preserved": True,
        "strong_origin_mutated": False,
        "result_used_to_define_controller": False,
        "causal_attribution": False,
    }
    Path("whole_flow_control_v2_24_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("WHOLE_FLOW_CONTROL_V2_24 " + json.dumps(summary, separators=(",", ":")))


MODE_DESCRIPTION = {
    "push": {"condition": "2/3 relation axes favorable and 2/3 axis movements favorable", "gate_magnitude": 0.04},
    "maintain": {"condition": "relation majority unfavorable but movement majority favorable, or warmup", "gate_magnitude": 0.04},
    "stop": {"condition": "relation majority favorable but movement majority unfavorable", "gate_magnitude": 0.02},
    "switch": {"condition": "relation majority unfavorable and movement majority unfavorable", "gate_magnitude": 0.0},
}


if __name__ == "__main__":
    main()
