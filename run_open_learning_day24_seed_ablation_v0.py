#!/usr/bin/env python3
"""Day24 seed ablation for Open Learning seed 6201.

Paired same-seed observation:
A = unchanged current model
B = remove only BUY_SEED WHEAT actions on Day24
No broader closure rule is introduced.
"""
import copy
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

SEED=6201
SEAT=0
OPPONENT=base.OPPONENT
OUT=Path("open_learning_day24_seed_ablation_v0.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(remove_day24_seed):
    configure()
    closes={}
    removed=[]
    last_day=None
    last_state=None

    def agent(obs):
        nonlocal last_day,last_state
        day=int(obs.get("day",0) or 0)
        state=observe_state(obs)
        if last_day is not None and day != last_day and last_state is not None:
            closes[last_day]=last_state
        last_day=day
        last_state=state

        actions=combat.agent(obs)
        if remove_day24_seed and day==24 and isinstance(actions,dict):
            market=list(actions.get("market",[]) or [])
            kept=[]
            for a in market:
                if isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="BUY_SEED" and a[1]=="WHEAT":
                    removed.append(copy.deepcopy(a))
                else:
                    kept.append(a)
            if len(kept)!=len(market):
                actions=copy.deepcopy(actions)
                actions["market"]=kept
        return actions

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    if last_day is not None and last_state is not None:
        closes[last_day]=last_state

    rewards=[float(s.reward) for s in env.state]
    return {
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "removed":removed,
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
    baseline=play(False)
    ablated=play(True)
    payload={
        "schema":"kaggriculture.open-learning-day24-seed-ablation.v0",
        "case":{"seed":SEED,"seat":SEAT},
        "baseline":baseline,
        "ablated":ablated,
        "diff":{
            "terminal_self":ablated["terminal"]["self"]-baseline["terminal"]["self"],
            "terminal_margin":ablated["terminal"]["margin"]-baseline["terminal"]["margin"],
        },
        "boundary":[
            "This tests only removal of Day24 BUY_SEED WHEAT actions.",
            "It does not establish temporal_realization as a layer.",
            "Ablation effect may reflect candidate quality, relation comparison, temporal realization, or interaction among them.",
            "No learning is auto-adopted."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPEN_LEARNING_DAY24_SEED_ABLATION "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
