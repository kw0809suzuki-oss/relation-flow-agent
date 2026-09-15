#!/usr/bin/env python3
"""Balanced score sweep after v2.7.

Keep both observed directions alive:
- self-preserving neighborhood around G2_D2/G2_D3
- margin-growing neighborhood around G4_D2/G4_D3

Do not force one scalar ranking. Report wins first, then a Pareto frontier over
(mean self delta, mean margin delta), with telemetry retained for context only.
"""

import copy
import json
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as baseline_agent
import full_strong_origin_v2_6_fat_sweep as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
SEEDS = tuple(range(3812, 3820))
CASES = tuple((seed, (seed - 3812) % 2) for seed in SEEDS)

CONFIGS = (
    {"name": "S22_B2", "min_day_gap": 2, "max_target_distance": 2, "episode_budget": 2},
    {"name": "S22_B3", "min_day_gap": 2, "max_target_distance": 2, "episode_budget": 3},
    {"name": "S22_B4", "min_day_gap": 2, "max_target_distance": 2, "episode_budget": 4},
    {"name": "B23_B2", "min_day_gap": 2, "max_target_distance": 3, "episode_budget": 2},
    {"name": "B23_B3", "min_day_gap": 2, "max_target_distance": 3, "episode_budget": 3},
    {"name": "M42_B2", "min_day_gap": 4, "max_target_distance": 2, "episode_budget": 2},
    {"name": "M42_B3", "min_day_gap": 4, "max_target_distance": 2, "episode_budget": 3},
    {"name": "M42_B4", "min_day_gap": 4, "max_target_distance": 2, "episode_budget": 4},
    {"name": "M43_B3", "min_day_gap": 4, "max_target_distance": 3, "episode_budget": 3},
)


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


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


def summarize(rows):
    self_d = [r["self_delta"] for r in rows]
    margin_d = [r["margin_delta"] for r in rows]
    totals = Counter()
    for row in rows:
        for key, value in row["telemetry"].get("fat_sweep", {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] += value
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
        "action_differences": sum(r["action_difference_count"] for r in rows),
        "episodes_started": totals.get("episodes_started", 0),
        "episode_overrides": totals.get("episode_overrides", 0),
        "fertilize_actions": totals.get("fertilize_actions", 0),
    }


def pareto_frontier(points):
    frontier = []
    for p in points:
        dominated = False
        for q in points:
            if q is p:
                continue
            at_least_as_good = (
                q["candidate_wins"] >= p["candidate_wins"]
                and q["mean_self_delta"] >= p["mean_self_delta"]
                and q["mean_margin_delta"] >= p["mean_margin_delta"]
            )
            strictly_better = (
                q["candidate_wins"] > p["candidate_wins"]
                or q["mean_self_delta"] > p["mean_self_delta"]
                or q["mean_margin_delta"] > p["mean_margin_delta"]
            )
            if at_least_as_good and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(p)
    return sorted(frontier, key=lambda x: (x["candidate_wins"], x["mean_self_delta"], x["mean_margin_delta"]), reverse=True)


def main():
    baselines = {(seed, seat): play(seed, seat, baseline_agent) for seed, seat in CASES}
    results = []
    for config in CONFIGS:
        candidate_agent.set_config(config)
        rows = []
        for seed, seat in CASES:
            base = baselines[(seed, seat)]
            cand = play(seed, seat, candidate_agent)
            rows.append({
                "seed": seed,
                "seat": seat,
                "self_delta": cand["score"]["self"] - base["score"]["self"],
                "margin_delta": cand["score"]["margin"] - base["score"]["margin"],
                "candidate_win": cand["score"]["win"],
                "action_difference_count": sum(a != b for a, b in zip(cand["actions"], base["actions"])),
                "telemetry": cand["telemetry"],
            })
        results.append({"config": config, "summary": summarize(rows), "rows": rows})

    points = [{"name": r["config"]["name"], **r["summary"]} for r in results]
    frontier = pareto_frontier(points)
    out = {
        "schema": "kaggriculture.full-v2-8-balanced-frontier.v1",
        "baseline": "full_strong_origin_v1.py",
        "same_seed_cases": list(CASES),
        "configs": list(CONFIGS),
        "results": results,
        "pareto_frontier": frontier,
        "all_points": points,
        "evaluation_policy": "observe terminal results; keep non-dominated self/margin directions; do not translate result into mechanism",
        "causal_attribution": False,
    }
    Path("full_v2_8_balanced_frontier_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("FULL_V2_8_FRONTIER " + json.dumps(frontier, ensure_ascii=False, separators=(",", ":")))
    print("FULL_V2_8_ALL " + json.dumps(points, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
