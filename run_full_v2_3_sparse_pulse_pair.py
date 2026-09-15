#!/usr/bin/env python3
"""Fresh-12 paired evaluation: Full v1 vs Whole v2.3 sparse pulse."""

import copy
import json
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as baseline_agent
import full_strong_origin_v2_3_sparse_pulse as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3762) % 2) for seed in range(3762, 3774))


def score(rewards, seat):
    own = float(rewards[seat])
    opponent = float(rewards[1 - seat])
    return {"self": own, "opponent": opponent, "margin": own - opponent, "win": own > opponent}


def play(seed, seat, module):
    module.reset_telemetry()
    actions = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        action = module.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {"score": score(rewards, seat), "actions": actions, "telemetry": module.get_telemetry()}


def first_difference(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return None


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, baseline_agent)
        candidate = play(seed, seat, candidate_agent)
        delta = {key: candidate["score"][key] - baseline["score"][key] for key in ("self", "opponent", "margin")}
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": baseline["score"],
            "candidate": candidate["score"],
            "terminal_delta": delta,
            "self_direction": "improved" if delta["self"] > 0 else "worsened" if delta["self"] < 0 else "equal",
            "margin_direction": "improved" if delta["margin"] > 0 else "worsened" if delta["margin"] < 0 else "equal",
            "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
            "action_difference_count": sum(a != b for a, b in zip(candidate["actions"], baseline["actions"])),
            "candidate_telemetry": candidate["telemetry"],
        })

    self_deltas = [row["terminal_delta"]["self"] for row in rows]
    margin_deltas = [row["terminal_delta"]["margin"] for row in rows]
    totals = Counter()
    for row in rows:
        for key, value in row["candidate_telemetry"].get("whole_v2_3", {}).items():
            if isinstance(value, (int, float)):
                totals[key] += value

    summary = {
        "case_count": len(rows),
        "mean_self_delta": statistics.mean(self_deltas),
        "median_self_delta": statistics.median(self_deltas),
        "self_direction_counts": dict(Counter(row["self_direction"] for row in rows)),
        "mean_margin_delta": statistics.mean(margin_deltas),
        "median_margin_delta": statistics.median(margin_deltas),
        "margin_direction_counts": dict(Counter(row["margin_direction"] for row in rows)),
        "baseline_wins": sum(row["baseline"]["win"] for row in rows),
        "candidate_wins": sum(row["candidate"]["win"] for row in rows),
        "action_difference_cases": sum(row["first_action_difference"] is not None for row in rows),
        "total_action_differences": sum(row["action_difference_count"] for row in rows),
        "whole_v2_3_totals": dict(totals),
    }

    result = {
        "schema": "kaggriculture.full-v2-3-sparse-pulse-pair.v1",
        "question": "does reducing only intervention frequency further reduce downside?",
        "baseline": "full_strong_origin_v1.py",
        "candidate": "full_strong_origin_v2_3_sparse_pulse.py",
        "cases": rows,
        "summary": summary,
        "runtime_inputs_excluded": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "baseline_mutated": False,
        "causal_attribution": False,
        "evaluation_policy": "short-loop probe; self score first, terminal direction and intervention dose second",
    }
    Path("full_v2_3_sparse_pulse_pair_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("FULL_V2_3_SPARSE_PULSE_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
