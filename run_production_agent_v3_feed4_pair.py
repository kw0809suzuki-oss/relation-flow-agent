#!/usr/bin/env python3
"""Paired evaluation: Production v3 FEED_CARRY=4 vs frozen Production v3 FEED_CARRY=5.

Single recovered fixed point only. Primary order:
self score -> margin -> win, with feed/livestock action counts retained for observation.
"""

import json
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import production_agent_v3_expansion_bridge as baseline_agent
import production_agent_v3_feed4 as candidate_agent

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
    return {
        "score": score(rewards, seat),
        "actions": dict(counts),
        "telemetry": module.get_telemetry(),
    }


def summary(vals):
    return {
        "mean": statistics.mean(vals),
        "median": statistics.median(vals),
        "positive": sum(v > 0 for v in vals),
        "negative": sum(v < 0 for v in vals),
        "zero": sum(v == 0 for v in vals),
    }


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
            "feed_delta": int(cand["actions"].get("FEED", 0)) - int(base["actions"].get("FEED", 0)),
            "care_delta": int(cand["actions"].get("CARE", 0)) - int(base["actions"].get("CARE", 0)),
            "harvest_delta": int(cand["actions"].get("HARVEST", 0)) - int(base["actions"].get("HARVEST", 0)),
            "candidate_win": cand["score"]["win"],
        })

    out_summary = {
        "cases": len(rows),
        "self_delta": summary([r["self_delta"] for r in rows]),
        "margin_delta": summary([r["margin_delta"] for r in rows]),
        "feed_delta": summary([r["feed_delta"] for r in rows]),
        "care_delta": summary([r["care_delta"] for r in rows]),
        "harvest_delta": summary([r["harvest_delta"] for r in rows]),
        "baseline_wins": sum(r["baseline"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate_win"] for r in rows),
    }

    out = {
        "schema": "kaggriculture.production-v3-feed4-pair.v1",
        "baseline": "production_agent_v3_expansion_bridge.py (FEED_CARRY=5)",
        "candidate": "production_agent_v3_feed4.py (FEED_CARRY=4)",
        "single_change": "FEED_CARRY 5 -> 4",
        "observation_boundary": {
            "bundle_used_for_control": False,
            "relation_used_for_control": False,
            "flow_used_for_control": False,
            "causal_attribution": False,
        },
        "cases": rows,
        "summary": out_summary,
    }
    Path("production_agent_v3_feed4_pair_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print("PRODUCTION_V3_FEED4_PAIR " + json.dumps(out_summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
