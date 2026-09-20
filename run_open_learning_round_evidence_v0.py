#!/usr/bin/env python3
"""Minimal cross-resource evidence for Open Learning Round seed 6204.

Observe late-horizon money-changing actions across resources. No intervention.
"""
import json, os
from collections import Counter, defaultdict
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

SEED=6204
SEAT=1
START_DAY=23
END_DAY=29
OPPONENT=base.OPPONENT
OUT=Path("open_learning_round_evidence_v0.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    by_day=defaultdict(lambda:{"calls":0,"first":None,"last":None,"market":[]})

    def agent(obs):
        day=int(obs.get("day",0) or 0)
        state=observe_state(obs)
        actions=combat.agent(obs)
        if START_DAY<=day<=END_DAY:
            rec=by_day[day]
            rec["calls"]+=1
            if rec["first"] is None: rec["first"]=state
            rec["last"]=state
            if isinstance(actions,dict):
                rec["market"].extend(list(actions.get("market",[]) or []))
        return actions

    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]

    rows=[]
    totals=Counter()
    quantities=Counter()
    for day in range(START_DAY,END_DAY+1):
        rec=by_day.get(day)
        if not rec: continue
        kinds=Counter()
        q=Counter()
        for a in rec["market"]:
            if not a: continue
            key=str(a[0])
            subject=str(a[1]) if len(a)>1 else ""
            label=key+(":"+subject if subject else "")
            kinds[label]+=1
            if len(a)>2 and isinstance(a[2],(int,float)):
                q[label]+=a[2]
            totals[label]+=1
            if len(a)>2 and isinstance(a[2],(int,float)):
                quantities[label]+=a[2]
        rows.append({
            "day":day,
            "remaining":rec["first"]["time"]["remaining_days"],
            "calls":rec["calls"],
            "first_money":rec["first"]["money"]["self"],
            "last_money":rec["last"]["money"]["self"],
            "first_seed_wheat":rec["first"]["flow_inputs"]["seed_inventory"]["WHEAT"],
            "last_seed_wheat":rec["last"]["flow_inputs"]["seed_inventory"]["WHEAT"],
            "last_planted":rec["last"]["capacity"]["planted_tiles"],
            "last_harvestable":rec["last"]["flow_outputs"]["harvestable_tiles"],
            "last_hands":rec["last"]["capacity"]["hands"],
            "last_cows":rec["last"]["capacity"]["cows"],
            "action_counts":dict(kinds),
            "action_quantities":dict(q),
        })

    payload={
        "schema":"kaggriculture.open-learning-round-evidence.v0",
        "case":{"seed":SEED,"seat":SEAT},
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "window":[START_DAY,END_DAY],
        "rows":rows,
        "totals":{"counts":dict(totals),"quantities":dict(quantities)},
        "boundary":[
            "Observation only; no intervention.",
            "Resources are observed without assuming temporal_realization is correct.",
            "This evidence is intended to distinguish seed-specific from cross-resource late investment structure."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPEN_LEARNING_ROUND_EVIDENCE "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
