#!/usr/bin/env python3
"""Paired whole-agent evaluation: current G5+ROI baseline vs Full Strong Origin v1."""

import copy
import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3512) % 2) for seed in range(3512, 3562))


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
            "direction": "improved" if delta["margin"] > 0 else "worsened" if delta["margin"] < 0 else "equal",
            "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
            "action_difference_count": sum(a != b for a, b in zip(candidate["actions"], baseline["actions"])),
            "candidate_telemetry": candidate["telemetry"],
        })

    directions = Counter(row["direction"] for row in rows)
    deltas = [row["terminal_delta"]["margin"] for row in rows]
    full_totals = Counter()
    for row in rows:
        for key, value in row["candidate_telemetry"].get("full_v1", {}).items():
            if isinstance(value, (int, float)):
                full_totals[key] += value

    summary = {
        "case_count": len(rows),
        "mean_margin_delta": sum(deltas) / len(deltas),
        "baseline_wins": sum(row["baseline"]["win"] for row in rows),
        "candidate_wins": sum(row["candidate"]["win"] for row in rows),
        "direction_counts": dict(directions),
        "largest_improvement": max(deltas),
        "largest_worsening": min(deltas),
        "action_difference_cases": sum(row["first_action_difference"] is not None for row in rows),
        "total_action_differences": sum(row["action_difference_count"] for row in rows),
        "full_v1_totals": dict(full_totals),
    }
    result = {
        "schema": "kaggriculture.full-strong-origin-v1-pair.v1",
        "question": "does restoring a broad livestock/feed/care/revenue loop over the current G5+ROI body improve the whole agent?",
        "baseline": "strong_origin_g5_roi.py",
        "candidate": "full_strong_origin_v1.py",
        "cases": rows,
        "summary": summary,
        "runtime_inputs_excluded": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "baseline_mutated": False,
        "candidate_change_unit": "whole economic-loop composition: G5+ROI + historical G8 livestock/feed/care/revenue lane",
        "result_used_to_define_candidate": False,
        "causal_attribution": False,
        "evaluation_policy": "whole-first; prune after terminal observation",
    }
    Path("full_strong_origin_v1_pair_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("FULL_STRONG_ORIGIN_V1_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
