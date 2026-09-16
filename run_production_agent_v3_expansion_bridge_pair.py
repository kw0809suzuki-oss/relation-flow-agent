#!/usr/bin/env python3
"""Paired evaluation: Production v3 expansion bridge vs frozen Production v2.

Primary order of observation:
PLANT -> active/planted surface -> self score -> margin -> win.
Bundle / Relation / Flow are not used for runtime control.
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import production_agent_v2_capacity_bridge as baseline_agent
import production_agent_v3_expansion_bridge as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3942) % 2) for seed in range(3942, 3992))


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def surface(farm):
    active = 0
    planted = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile == "LOCKED" or tile is None:
                continue
            active += 1
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                planted += 1
    return {"active_tiles": active, "planted_tiles": planted}


def count_actions(action, counts):
    units = [action.get("farmer", ["PASS"])] + list(action.get("hands", []) or [])
    for a in units:
        if not a:
            continue
        counts[str(a[0])] += 1


def play(seed, seat, module):
    module.reset_telemetry()
    counts = Counter()

    def wrapped(obs):
        action = module.agent(obs)
        count_actions(action, counts)
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = wrapped
    env.run(players)
    rewards = [state.reward for state in env.state]
    final_obs = env.state[seat].observation
    farm = final_obs["farms"][seat]
    return {
        "score": score(rewards, seat),
        "surface": surface(farm),
        "actions": dict(counts),
        "telemetry": module.get_telemetry(),
    }


def delta(a, b):
    return float(a) - float(b)


def main():
    rows = []
    telemetry_total = Counter()

    for seed, seat in CASES:
        base = play(seed, seat, baseline_agent)
        cand = play(seed, seat, candidate_agent)
        t = cand["telemetry"].get("production_v3_expansion_bridge", {})
        for k in ("unlock_events", "targets_added", "bridge_worker_actions", "bridge_moves", "bridge_plants", "bridge_waters", "targets_completed"):
            telemetry_total[k] += int(t.get(k, 0))

        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": base["score"],
            "candidate": cand["score"],
            "plant_delta": int(cand["actions"].get("PLANT", 0)) - int(base["actions"].get("PLANT", 0)),
            "active_tiles_delta": int(cand["surface"]["active_tiles"]) - int(base["surface"]["active_tiles"]),
            "planted_tiles_delta": int(cand["surface"]["planted_tiles"]) - int(base["surface"]["planted_tiles"]),
            "self_delta": delta(cand["score"]["self"], base["score"]["self"]),
            "margin_delta": delta(cand["score"]["margin"], base["score"]["margin"]),
            "candidate_win": cand["score"]["win"],
        })

    def summary_for(key):
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
        "plant_delta": summary_for("plant_delta"),
        "active_tiles_delta": summary_for("active_tiles_delta"),
        "planted_tiles_delta": summary_for("planted_tiles_delta"),
        "self_delta": summary_for("self_delta"),
        "margin_delta": summary_for("margin_delta"),
        "baseline_wins": sum(r["baseline"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate_win"] for r in rows),
        "bridge_telemetry": dict(telemetry_total),
    }

    out = {
        "schema": "kaggriculture.production-agent-v3-expansion-bridge-pair.v1",
        "baseline": "production_agent_v2_capacity_bridge.py",
        "candidate": "production_agent_v3_expansion_bridge.py",
        "design_unit": "newly unlocked tile -> reserved trailing hand -> MOVE -> PLANT -> first WATER -> release",
        "observation_order": ["plant", "active_planted_surface", "self_score", "margin", "win"],
        "observation_boundary": {
            "bundle_used_for_control": False,
            "relation_used_for_control": False,
            "flow_used_for_control": False,
            "causal_attribution": False,
        },
        "cases": rows,
        "summary": summary,
    }
    Path("production_agent_v3_expansion_bridge_pair_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print("PRODUCTION_V3_EXPANSION_BRIDGE_PAIR " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
