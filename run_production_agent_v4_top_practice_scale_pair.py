#!/usr/bin/env python3
"""Paired evaluation: v4 top-practice scale bridge vs frozen v3.

Observation order: self -> margin -> win, with land/hands/action counts as support.
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import production_agent_v3_expansion_bridge as baseline_agent
import production_agent_v4_top_practice_scale as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3992) % 2) for seed in range(3992, 4042))


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def count_actions(action, counts):
    units = [action.get("farmer", ["PASS"])] + list(action.get("hands", []) or [])
    for a in units:
        if a:
            counts[str(a[0])] += 1
    for o in action.get("market", []) or []:
        if o:
            counts[f"MKT_{o[0]}"] += 1


def play(seed, seat, module):
    module.reset_telemetry()
    counts = Counter()
    final_hands = 0
    final_land = 0

    def wrapped(obs):
        nonlocal final_hands, final_land
        me = obs["farms"][seat]
        final_hands = len(me.get("hands", []) or [])
        final_land = len(me.get("unlocked_quadrants", []) or [])
        action = module.agent(obs)
        count_actions(action, counts)
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = wrapped
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {
        "score": score(rewards, seat),
        "actions": dict(counts),
        "final_hands": final_hands,
        "final_land": final_land,
        "telemetry": module.get_telemetry(),
    }


def main():
    rows = []
    telemetry_total = Counter()
    for seed, seat in CASES:
        base = play(seed, seat, baseline_agent)
        cand = play(seed, seat, candidate_agent)
        t = cand["telemetry"].get("production_v4_top_practice_scale", {})
        for k in ("extra_land_orders", "extra_hire_orders"):
            telemetry_total[k] += int(t.get(k, 0))
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": base["score"],
            "candidate": cand["score"],
            "self_delta": cand["score"]["self"] - base["score"]["self"],
            "margin_delta": cand["score"]["margin"] - base["score"]["margin"],
            "hands_delta": cand["final_hands"] - base["final_hands"],
            "land_delta": cand["final_land"] - base["final_land"],
            "plant_delta": cand["actions"].get("PLANT", 0) - base["actions"].get("PLANT", 0),
            "water_delta": cand["actions"].get("WATER", 0) - base["actions"].get("WATER", 0),
            "harvest_delta": cand["actions"].get("HARVEST", 0) - base["actions"].get("HARVEST", 0),
            "candidate_win": cand["score"]["win"],
        })

    def stats(key):
        vals = [r[key] for r in rows]
        return {
            "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "positive": sum(v > 0 for v in vals),
            "negative": sum(v < 0 for v in vals),
            "zero": sum(v == 0 for v in vals),
        }

    summary = {
        "cases": len(rows),
        "self_delta": stats("self_delta"),
        "margin_delta": stats("margin_delta"),
        "hands_delta": stats("hands_delta"),
        "land_delta": stats("land_delta"),
        "plant_delta": stats("plant_delta"),
        "water_delta": stats("water_delta"),
        "harvest_delta": stats("harvest_delta"),
        "baseline_wins": sum(r["baseline"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate_win"] for r in rows),
        "telemetry": dict(telemetry_total),
    }
    out = {
        "schema": "kaggriculture.production-v4-top-practice-scale-pair.v1",
        "baseline": "production_agent_v3_expansion_bridge.py",
        "candidate": "production_agent_v4_top_practice_scale.py",
        "design_unit": "midgame capacity envelope: up to 3 land + up to 10 hands",
        "observation_boundary": {
            "bundle_used_for_control": False,
            "relation_used_for_control": False,
            "flow_used_for_control": False,
            "causal_attribution": False,
        },
        "cases": rows,
        "summary": summary,
    }
    Path("production_agent_v4_top_practice_scale_pair_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print("PRODUCTION_V4_TOP_PRACTICE_SCALE_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
