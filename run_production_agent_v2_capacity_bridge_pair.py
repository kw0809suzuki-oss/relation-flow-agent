#!/usr/bin/env python3
"""Paired evaluation: Production v2 capacity bridge vs Production v1.

Front-side game design only. Bundle / Relation / Flow remain external observation
axes and are not used for runtime control.
"""

import json
import statistics
from pathlib import Path

from kaggle_environments import make

import production_agent_v1 as baseline_agent
import production_agent_v2_capacity_bridge as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3912) % 2) for seed in range(3912, 3942))


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
    bridge_land = 0
    bridge_hires = 0
    for seed, seat in CASES:
        base = play(seed, seat, baseline_agent)
        cand = play(seed, seat, candidate_agent)
        t = cand["telemetry"].get("production_v2_capacity_bridge", {})
        bridge_land += int(t.get("bridge_land_orders", 0))
        bridge_hires += int(t.get("bridge_hire_orders", 0))
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
        "bridge_land_orders": bridge_land,
        "bridge_hire_orders": bridge_hires,
    }
    out = {
        "schema": "kaggriculture.production-agent-v2-capacity-bridge-pair.v1",
        "baseline": "production_agent_v1.py",
        "candidate": "production_agent_v2_capacity_bridge.py",
        "design_unit": "day7-8 bounded land/hands capacity bridge into existing production scheduler",
        "observation_boundary": {
            "bundle_used_for_control": False,
            "relation_used_for_control": False,
            "flow_used_for_control": False,
        },
        "cases": rows,
        "summary": summary,
        "causal_attribution": False,
    }
    Path("production_agent_v2_capacity_bridge_pair_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print("PRODUCTION_V2_CAPACITY_BRIDGE_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
