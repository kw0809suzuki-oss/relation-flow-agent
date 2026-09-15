#!/usr/bin/env python3
"""v3.0 boundary-preserving economic-loop sweep.

Purpose:
- keep observation axes observational only
- generate action candidates only from known game-side economic knobs
- compare terminal outcomes on identical fresh seeds

This evaluator does not derive controls from Bundle / Relation / Flow labels.
Those remain comparison surfaces only.
"""

import copy
import json
import statistics
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as candidate_agent
import full_strong_origin_v1 as baseline_agent

OPPONENT = "opponents/seyamalam_v21.py"
SEEDS = tuple(range(3830, 3842))
CASES = tuple((seed, (seed - 3830) % 2) for seed in SEEDS)

BASE_COW_TARGETS = ((5, 2), (9, 4), (14, 6), (20, 8))
BASE_FEED_CARRY = 4

CONFIGS = (
    {"name": "BASE", "cow_targets": BASE_COW_TARGETS, "feed_carry": 4},
    {"name": "LEAN", "cow_targets": ((6, 2), (11, 3), (16, 5), (21, 6)), "feed_carry": 3},
    {"name": "EARLY", "cow_targets": ((4, 2), (8, 4), (13, 6), (18, 8)), "feed_carry": 4},
    {"name": "DELAYED", "cow_targets": ((7, 2), (11, 4), (16, 6), (22, 8)), "feed_carry": 4},
    {"name": "HEAVY", "cow_targets": ((5, 2), (9, 4), (14, 7), (20, 9)), "feed_carry": 5},
    {"name": "FEED5", "cow_targets": BASE_COW_TARGETS, "feed_carry": 5},
)


def set_config(config):
    candidate_agent.COW_TARGETS = tuple(tuple(x) for x in config["cow_targets"])
    candidate_agent.FEED_CARRY = int(config["feed_carry"])


def reset_base():
    candidate_agent.COW_TARGETS = BASE_COW_TARGETS
    candidate_agent.FEED_CARRY = BASE_FEED_CARRY


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def play(seed, seat):
    candidate_agent.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = candidate_agent.agent
    env.run(players)
    rewards = [state.reward for state in env.state]
    return score(rewards, seat)


def summarize(rows):
    self_d = [r["self_delta"] for r in rows]
    margin_d = [r["margin_delta"] for r in rows]
    return {
        "cases": len(rows),
        "mean_self_delta": statistics.mean(self_d),
        "median_self_delta": statistics.median(self_d),
        "self_improved": sum(x > 0 for x in self_d),
        "self_worsened": sum(x < 0 for x in self_d),
        "mean_margin_delta": statistics.mean(margin_d),
        "median_margin_delta": statistics.median(margin_d),
        "margin_improved": sum(x > 0 for x in margin_d),
        "margin_worsened": sum(x < 0 for x in margin_d),
        "candidate_wins": sum(r["candidate_win"] for r in rows),
    }


def main():
    reset_base()
    baselines = {(seed, seat): play(seed, seat) for seed, seat in CASES}

    results = []
    for config in CONFIGS:
        set_config(config)
        rows = []
        for seed, seat in CASES:
            base = baselines[(seed, seat)]
            cand = play(seed, seat)
            rows.append({
                "seed": seed,
                "seat": seat,
                "self_delta": cand["self"] - base["self"],
                "margin_delta": cand["margin"] - base["margin"],
                "candidate_win": cand["win"],
                "candidate_self": cand["self"],
                "candidate_margin": cand["margin"],
            })
        results.append({"config": config, "summary": summarize(rows), "rows": rows})

    reset_base()
    out = {
        "schema": "kaggriculture.v3-0-economic-loop-sweep.v1",
        "purpose": "terminal score/win improvement with observation-control boundary preserved",
        "baseline": {"cow_targets": BASE_COW_TARGETS, "feed_carry": BASE_FEED_CARRY},
        "same_seed_cases": list(CASES),
        "results": results,
        "observation_boundary": {
            "bundle_used_for_control": False,
            "relation_used_for_control": False,
            "flow_used_for_control": False,
            "terminal_used_for_comparison_only": True,
        },
        "causal_attribution": False,
    }
    Path("v3_0_economic_loop_sweep_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print("V3_0_ECONOMIC_LOOP_SWEEP " + json.dumps(
        [{"name": r["config"]["name"], **r["summary"]} for r in results],
        ensure_ascii=False,
        separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
