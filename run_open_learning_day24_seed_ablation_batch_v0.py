#!/usr/bin/env python3
"""Fresh-case Day24 seed ablation batch for Open Learning.

Tests seeds 6202/6203 with the same narrow intervention used on 6201.
No taxonomy label is adopted from this comparison.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

CASES=[(6202,1),(6203,0)]
OPPONENT=base.OPPONENT
OUT=Path("open_learning_day24_seed_ablation_batch_v0.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(seed,seat,remove):
    configure()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    closes={}
    removed=[]
    last_day=None
    last_state=None
    def agent(obs):
        nonlocal last_day,last_state
        day=int(obs.get("day",0) or 0)
        state=observe_state(obs)
        if last_day is not None and day!=last_day and last_state is not None:
            closes[last_day]=last_state
        last_day=day; last_state=state
        actions=combat.agent(obs)
        if remove and day==24 and isinstance(actions,dict):
            market=list(actions.get("market",[]) or [])
            kept=[]
            for a in market:
                if isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="BUY_SEED" and a[1]=="WHEAT":
                    removed.append(copy.deepcopy(a))
                else:
                    kept.append(a)
            if len(kept)!=len(market):
                actions=copy.deepcopy(actions); actions["market"]=kept
        return actions
    players=[OPPONENT,OPPONENT]; players[seat]=agent
    env.run(players)
    if last_day is not None and last_state is not None: closes[last_day]=last_state
    rewards=[float(x.reward) for x in env.state]
    return {
        "terminal":{"self":rewards[seat],"opponent":rewards[1-seat],"margin":rewards[seat]-rewards[1-seat]},
        "removed_count":len(removed),
        "removed_examples":removed[:5],
        "closing":{
            str(d):{
                "money":closes[d]["money"]["self"],
                "seed_wheat":closes[d]["flow_inputs"]["seed_inventory"]["WHEAT"],
                "harvestable":closes[d]["flow_outputs"]["harvestable_tiles"],
                "planted":closes[d]["capacity"]["planted_tiles"],
                "hands":closes[d]["capacity"]["hands"],
                "cows":closes[d]["capacity"]["cows"],
            } for d in sorted(closes) if 24<=d<=29
        }
    }

def main():
    rows=[]
    for seed,seat in CASES:
        base_run=play(seed,seat,False)
        ab=play(seed,seat,True)
        rows.append({
            "seed":seed,"seat":seat,
            "baseline":base_run,"ablated":ab,
            "diff":{
                "terminal_self":ab["terminal"]["self"]-base_run["terminal"]["self"],
                "terminal_margin":ab["terminal"]["margin"]-base_run["terminal"]["margin"],
                "terminal_seed_wheat":ab["closing"]["29"]["seed_wheat"]-base_run["closing"]["29"]["seed_wheat"],
                "terminal_harvestable":ab["closing"]["29"]["harvestable"]-base_run["closing"]["29"]["harvestable"],
                "terminal_planted":ab["closing"]["29"]["planted"]-base_run["closing"]["29"]["planted"],
            }
        })
    payload={
        "schema":"kaggriculture.open-learning-day24-seed-ablation-batch.v0",
        "cases":rows,
        "boundary":[
            "Only Day24 BUY_SEED WHEAT is removed.",
            "Same intervention as seed 6201 is reused for replication, not generalized as a rule.",
            "Repeated effects strengthen an observation candidate but do not create a taxonomy layer automatically.",
            "No learning is auto-adopted."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPEN_LEARNING_DAY24_SEED_BATCH "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
