#!/usr/bin/env python3
"""Paired terminal evaluation: G5+ROI baseline vs G5+ROI+cash-out."""

import copy
import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import strong_origin_g5_roi as baseline_agent
import strong_origin_g5_roi_cashout as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3462) % 2) for seed in range(3462, 3512))


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
    cashout_totals = {
        "seed_orders_kept": 0,
        "seed_orders_filtered": 0,
        "seed_units_kept": 0,
        "seed_units_filtered": 0,
        "filtered_by_crop": {"WHEAT": 0, "STRAWBERRY": 0, "MELON": 0},
    }
    for row in rows:
        c = row["candidate_telemetry"]["cashout"]
        for key in ("seed_orders_kept", "seed_orders_filtered", "seed_units_kept", "seed_units_filtered"):
            cashout_totals[key] += c[key]
        for crop, value in c["filtered_by_crop"].items():
            cashout_totals["filtered_by_crop"][crop] += value

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
        "cashout_totals": cashout_totals,
    }
    result = {
        "schema": "kaggriculture.strong-origin-g5-roi-cashout-pair.v1",
        "question": "does late crop reinvestment cash-out improve terminal results over G5+ROI?",
        "baseline": "strong_origin_g5_roi.py",
        "candidate": "strong_origin_g5_roi_cashout.py",
        "cases": rows,
        "summary": summary,
        "runtime_inputs_excluded": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "candidate_change_unit": "late crop seed reinvestment cutoffs only",
        "result_used_to_define_candidate": False,
        "causal_attribution": False,
    }
    Path("strong_origin_g5_roi_cashout_pair_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("STRONG_ORIGIN_G5_ROI_CASHOUT_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
