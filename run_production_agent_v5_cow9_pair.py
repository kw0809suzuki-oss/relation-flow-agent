#!/usr/bin/env python3
"""Fresh10 paired evaluation: v5 Cow9 vs frozen v3."""

import json
import statistics
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import production_agent_v3_expansion_bridge as baseline_agent
import production_agent_v5_cow9 as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 4042) % 2) for seed in range(4042, 4052))


def score(rewards, seat):
    own = float(rewards[seat]); opp = float(rewards[1-seat])
    return {"self": own, "opponent": opp, "margin": own-opp, "win": own>opp}


def count_actions(action, counts):
    for a in [action.get("farmer", ["PASS"]), *list(action.get("hands", []) or [])]:
        if a: counts[str(a[0])] += 1
    for o in action.get("market", []) or []:
        if o:
            counts[f"MKT_{o[0]}"] += 1
            if o[0] == "BUY_ANIMAL" and len(o) > 1:
                counts[f"BUY_ANIMAL_{o[1]}"] += int(o[2]) if len(o) > 2 else 1


def cow_count(me):
    total = 0
    for row in me.get("tiles", []) or []:
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                total += 1
    return total


def play(seed, seat, module):
    module.reset_telemetry(); counts = Counter(); final_cows = 0
    def wrapped(obs):
        nonlocal final_cows
        final_cows = cow_count(obs["farms"][seat])
        action = module.agent(obs)
        count_actions(action, counts)
        return action
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]; players[seat] = wrapped
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {"score": score(rewards, seat), "actions": dict(counts), "final_cows": final_cows}


def stat(rows, key):
    vals=[r[key] for r in rows]
    return {"mean": statistics.mean(vals), "median": statistics.median(vals),
            "positive": sum(v>0 for v in vals), "negative": sum(v<0 for v in vals), "zero": sum(v==0 for v in vals)}


def main():
    rows=[]
    for seed, seat in CASES:
        b=play(seed, seat, baseline_agent); c=play(seed, seat, candidate_agent)
        rows.append({
            "seed":seed,"seat":seat,"baseline":b["score"],"candidate":c["score"],
            "self_delta":c["score"]["self"]-b["score"]["self"],
            "margin_delta":c["score"]["margin"]-b["score"]["margin"],
            "cow_delta":c["final_cows"]-b["final_cows"],
            "buy_cow_delta":c["actions"].get("BUY_ANIMAL_COW",0)-b["actions"].get("BUY_ANIMAL_COW",0),
            "feed_delta":c["actions"].get("FEED",0)-b["actions"].get("FEED",0),
            "care_delta":c["actions"].get("CARE",0)-b["actions"].get("CARE",0),
            "harvest_delta":c["actions"].get("HARVEST",0)-b["actions"].get("HARVEST",0),
        })
    summary={
        "cases":len(rows),
        "self_delta":stat(rows,"self_delta"),"margin_delta":stat(rows,"margin_delta"),
        "cow_delta":stat(rows,"cow_delta"),"buy_cow_delta":stat(rows,"buy_cow_delta"),
        "feed_delta":stat(rows,"feed_delta"),"care_delta":stat(rows,"care_delta"),"harvest_delta":stat(rows,"harvest_delta"),
        "baseline_wins":sum(r["baseline"]["win"] for r in rows),
        "candidate_wins":sum(r["candidate"]["win"] for r in rows),
    }
    out={"schema":"kaggriculture.production-v5-cow9-pair.v1","baseline":"production_agent_v3_expansion_bridge.py",
         "candidate":"production_agent_v5_cow9.py","design_unit":"Cow target 8 -> 9 only",
         "observation_boundary":{"bundle_used_for_control":False,"relation_used_for_control":False,"flow_used_for_control":False,"causal_attribution":False},
         "cases":rows,"summary":summary}
    Path("production_agent_v5_cow9_pair_result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("PRODUCTION_V5_COW9_PAIR "+json.dumps(summary,separators=(",",":")))

if __name__=="__main__": main()
