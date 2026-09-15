#!/usr/bin/env python3
"""Same-seed coarse sweep around Full v2.4.

Goal: fatten first, prune later. Compare several nearby intervention shapes on
identical seeds and keep only externally better directions.
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
SEEDS = tuple(range(3798, 3804))
CASES = tuple((seed, (seed - 3798) % 2) for seed in SEEDS)

CONFIGS = (
    {"name": "A_center", "min_day_gap": 2, "max_target_distance": 2, "episode_budget": 3},
    {"name": "B_faster", "min_day_gap": 1, "max_target_distance": 2, "episode_budget": 3},
    {"name": "C_slower", "min_day_gap": 3, "max_target_distance": 2, "episode_budget": 3},
    {"name": "D_narrow", "min_day_gap": 2, "max_target_distance": 1, "episode_budget": 3},
    {"name": "E_wider", "min_day_gap": 2, "max_target_distance": 3, "episode_budget": 3},
    {"name": "F_short", "min_day_gap": 2, "max_target_distance": 2, "episode_budget": 2},
    {"name": "G_long", "min_day_gap": 2, "max_target_distance": 2, "episode_budget": 4},
    {"name": "H_fast_wide", "min_day_gap": 1, "max_target_distance": 3, "episode_budget": 3},
    {"name": "I_slow_wide_long", "min_day_gap": 3, "max_target_distance": 3, "episode_budget": 4},
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


def main():
    baselines = {}
    for seed, seat in CASES:
        baselines[(seed, seat)] = play(seed, seat, baseline_agent)

    results = []
    for config in CONFIGS:
        candidate_agent.set_config(config)
        rows = []
        for seed, seat in CASES:
            base = baselines[(seed, seat)]
            cand = play(seed, seat, candidate_agent)
            self_delta = cand["score"]["self"] - base["score"]["self"]
            margin_delta = cand["score"]["margin"] - base["score"]["margin"]
            action_diff = sum(a != b for a, b in zip(cand["actions"], base["actions"]))
            rows.append({
                "seed": seed,
                "seat": seat,
                "self_delta": self_delta,
                "margin_delta": margin_delta,
                "candidate_win": cand["score"]["win"],
                "action_difference_count": action_diff,
                "telemetry": cand["telemetry"],
            })
        summary = summarize(rows)
        results.append({"config": config, "summary": summary, "rows": rows})

    ranking = sorted(
        ({"name": r["config"]["name"], **r["summary"]} for r in results),
        key=lambda x: (x["candidate_wins"], x["mean_margin_delta"], x["mean_self_delta"]),
        reverse=True,
    )

    out = {
        "schema": "kaggriculture.full-v2-6-fat-sweep.v1",
        "baseline": "full_strong_origin_v1.py",
        "same_seed_cases": list(CASES),
        "configs": list(CONFIGS),
        "results": results,
        "ranking": ranking,
        "evaluation_policy": "fatten then prune; rank by wins, mean margin, then mean self; external terminal first",
        "runtime_inputs_excluded": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "causal_attribution": False,
    }
    Path("full_v2_6_fat_sweep_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("FULL_V2_6_FAT_SWEEP " + json.dumps(ranking, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
