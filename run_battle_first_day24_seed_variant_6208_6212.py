#!/usr/bin/env python3
"""Battle-first paired Day24 WHEAT-seed suppression on 6208-6212.

Keep the intervention narrow:
baseline vs remove only Day24 BUY_SEED WHEAT.
Judge terminal first; do not deep-dive per case in this batch.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

CASES=[(6208,1),(6209,0),(6210,1),(6211,0),(6212,1)]
OPPONENT=base.OPPONENT
OUT=Path("battle_first_day24_seed_variant_6208_6212.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(seed,seat,suppress):
    configure()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    closes={}
    last_day=None
    last_state=None
    removed=[]

    def agent(obs):
        nonlocal last_day,last_state
        day=int(obs.get("day",0) or 0)
        state=observe_state(obs)
        if last_day is not None and day!=last_day and last_state is not None:
            closes[last_day]=last_state
        last_day=day
        last_state=state

        actions=combat.agent(obs)
        if suppress and day==24 and isinstance(actions,dict):
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

    players=[OPPONENT,OPPONENT]
    players[seat]=agent
    env.run(players)

    if last_day is not None and last_state is not None:
        closes[last_day]=last_state

    rewards=[float(x.reward) for x in env.state]
    end=closes.get(29,{})
    return {
        "terminal":{
            "self":rewards[seat],
            "opponent":rewards[1-seat],
            "margin":rewards[seat]-rewards[1-seat],
            "win_loss":"win" if rewards[seat]>rewards[1-seat] else "loss" if rewards[seat]<rewards[1-seat] else "draw",
        },
        "removed_count":len(removed),
        "removed_examples":removed[:5],
        "terminal_state":{
            "seed_wheat":end.get("flow_inputs",{}).get("seed_inventory",{}).get("WHEAT"),
            "planted":end.get("capacity",{}).get("planted_tiles"),
            "harvestable":end.get("flow_outputs",{}).get("harvestable_tiles"),
            "hands":end.get("capacity",{}).get("hands"),
            "cows":end.get("capacity",{}).get("cows"),
        }
    }

def main():
    rows=[]
    for seed,seat in CASES:
        baseline=play(seed,seat,False)
        variant=play(seed,seat,True)
        rows.append({
            "seed":seed,
            "seat":seat,
            "baseline":baseline,
            "variant":variant,
            "diff":{
                "terminal_self":variant["terminal"]["self"]-baseline["terminal"]["self"],
                "terminal_margin":variant["terminal"]["margin"]-baseline["terminal"]["margin"],
                "terminal_seed_wheat":variant["terminal_state"]["seed_wheat"]-baseline["terminal_state"]["seed_wheat"],
                "terminal_planted":variant["terminal_state"]["planted"]-baseline["terminal_state"]["planted"],
                "terminal_harvestable":variant["terminal_state"]["harvestable"]-baseline["terminal_state"]["harvestable"],
            }
        })

    payload={
        "schema":"kaggriculture.battle-first-day24-seed-variant.v0",
        "cases":rows,
        "boundary":[
            "Only Day24 BUY_SEED WHEAT is suppressed.",
            "Primary judgment is terminal self/margin across the five Battles.",
            "Do not infer a general late-seed rule from this batch alone.",
            "No per-case deep dive, taxonomy promotion, or adoption is automatic."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BATTLE_FIRST_DAY24_SEED_VARIANT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
