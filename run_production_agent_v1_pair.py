#!/usr/bin/env python3
"""Paired evaluation for Production Agent v1.

This run evaluates the front-side production agent only. Observation Bundle /
Relation / Flow are explicitly excluded from runtime control.
"""

import json
import statistics
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as baseline_agent
import production_agent_v1 as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3842) % 2) for seed in range(3842, 3862))


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def play(seed, seat, module):
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = module.agent
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {"score": score(rewards, seat), "telemetry": module.get_telemetry()}


def main():
    rows = []
    for seed, seat in CASES:
        base = play(seed, seat, baseline_agent)
        cand = play(seed, seat, candidate_agent)
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": base["score"],
            "candidate": cand["score"],
            "self_delta": cand["score"]["self"] - base["score"]["self"],
            "margin_delta": cand["score"]["margin"] - base["score"]["margin"],
            "candidate_win": cand["score"]["win"],
        })

    self_d = [r["self_delta"] for r in rows]
    margin_d = [r["margin_delta"] for r in rows]
    summary = {
        "cases": len(rows),
        "mean_self_delta": statistics.mean(self_d),
        "median_self_delta": statistics.median(self_d),
        "self_improved": sum(x > 0 for x in self_d),
        "self_worsened": sum(x < 0 for x in self_d),
        "mean_margin_delta": statistics.mean(margin_d),
        "median_margin_delta": statistics.median(margin_d),
        "margin_improved": sum(x > 0 for x in margin_d),
        "margin_worsened": sum(x < 0 for x in margin_d),
        "baseline_wins": sum(r["baseline"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate_win"] for r in rows),
    }
    out = {
        "schema": "kaggriculture.production-agent-v1-pair.v1",
        "baseline": "full_strong_origin_v1.py",
        "candidate": "production_agent_v1.py",
        "surface_goal": "increase production/recovery/sale throughput under game rules",
        "observation_boundary": {
            "bundle_used_for_control": False,
            "relation_used_for_control": False,
            "flow_used_for_control": False,
        },
        "cases": rows,
        "summary": summary,
        "causal_attribution": False,
    }
    Path("production_agent_v1_pair_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("PRODUCTION_AGENT_V1_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
