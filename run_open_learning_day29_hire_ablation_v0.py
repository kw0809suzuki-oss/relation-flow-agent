#!/usr/bin/env python3
"""Cross-context minimal A/B for Open Learning seed 6204.

Remove only HIRE actions on Day29 (remaining horizon = 1).
This tests a different investment type than WHEAT seed.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

SEED=6204
SEAT=1
OPPONENT=base.OPPONENT
OUT=Path("open_learning_day29_hire_ablation_v0.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(remove_hire):
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
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
        last_day=day
        last_state=state

        actions=combat.agent(obs)
        if remove_hire and day==29 and isinstance(actions,dict):
            market=list(actions.get("market",[]) or [])
            kept=[]
            for a in market:
                if isinstance(a,(list,tuple)) and len(a)>=1 and a[0]=="HIRE":
                    removed.append(copy.deepcopy(a))
                else:
                    kept.append(a)
            if len(kept)!=len(market):
                actions=copy.deepcopy(actions)
                actions["market"]=kept
        return actions

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    if last_day is not None and last_state is not None:
        closes[last_day]=last_state
    rewards=[float(x.reward) for x in env.state]
    s=closes[29]
    return {
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "removed_count":len(removed),
        "day29_closing":{
            "money":s["money"]["self"],
            "hands":s["capacity"]["hands"],
            "cows":s["capacity"]["cows"],
            "planted":s["capacity"]["planted_tiles"],
            "harvestable":s["flow_outputs"]["harvestable_tiles"],
            "seed_wheat":s["flow_inputs"]["seed_inventory"]["WHEAT"],
            "product_inventory":s["flow_outputs"]["product_inventory"],
            "weeds":s["work_state"]["weeds"],
            "unwatered":s["work_state"]["unwatered_tiles"],
        }
    }

def main():
    baseline=play(False)
    ablated=play(True)
    payload={
        "schema":"kaggriculture.open-learning-day29-hire-ablation.v0",
        "case":{"seed":SEED,"seat":SEAT},
        "baseline":baseline,
        "ablated":ablated,
        "diff":{
            "terminal_self":ablated["terminal"]["self"]-baseline["terminal"]["self"],
            "terminal_margin":ablated["terminal"]["margin"]-baseline["terminal"]["margin"],
            "hands":ablated["day29_closing"]["hands"]-baseline["day29_closing"]["hands"],
            "planted":ablated["day29_closing"]["planted"]-baseline["day29_closing"]["planted"],
            "harvestable":ablated["day29_closing"]["harvestable"]-baseline["day29_closing"]["harvestable"],
            "weeds":ablated["day29_closing"]["weeds"]-baseline["day29_closing"]["weeds"],
            "unwatered":ablated["day29_closing"]["unwatered"]-baseline["day29_closing"]["unwatered"],
        },
        "boundary":[
            "Only Day29 HIRE actions are removed.",
            "This is a cross-context probe, not a HIRE rule.",
            "A result can support, weaken, or leave unresolved temporal_realization.",
            "No candidate maturity or adoption is updated automatically."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPEN_LEARNING_DAY29_HIRE_ABLATION "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
