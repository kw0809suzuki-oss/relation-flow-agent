#!/usr/bin/env python3
"""Battle-first 5-battle batch.

Run five unknown Battles without deep-dive interruption.
Record only terminal and a thin daily summary for one-candidate review afterward.
"""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

CASES=[(6208,1),(6209,0),(6210,1),(6211,0),(6212,1)]
OPPONENT=base.OPPONENT
OPPONENT_LABEL="Seyamalam v21"
OUT=Path("battle_first_batch_6208_6212.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(seed,seat):
    configure()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    daily=[]
    last_day=None
    def agent(obs):
        nonlocal last_day
        day=int(obs.get("day",0) or 0)
        s=observe_state(obs)
        row={
            "day":day,
            "remaining":s["time"]["remaining_days"],
            "self_money":s["money"]["self"],
            "opp_money":s["money"]["opponent"],
            "hands":s["capacity"]["hands"],
            "cows":s["capacity"]["cows"],
            "planted":s["capacity"]["planted_tiles"],
            "harvestable":s["flow_outputs"]["harvestable_tiles"],
            "seed_wheat":s["flow_inputs"]["seed_inventory"]["WHEAT"],
            "weeds":s["work_state"]["weeds"],
        }
        if day!=last_day:
            daily.append(row); last_day=day
        else:
            daily[-1]=row
        return combat.agent(obs)
    players=[OPPONENT,OPPONENT]; players[seat]=agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
        "seed":seed,"seat":seat,"opponent":OPPONENT_LABEL,
        "terminal":{
            "self":rewards[seat],
            "opponent":rewards[1-seat],
            "margin":rewards[seat]-rewards[1-seat],
            "win_loss":"win" if rewards[seat]>rewards[1-seat] else "loss" if rewards[seat]<rewards[1-seat] else "draw",
        },
        "daily":daily,
    }

def main():
    results=[play(seed,seat) for seed,seat in CASES]
    payload={
        "schema":"kaggriculture.battle-first-batch.v0",
        "cases":results,
        "boundary":[
            "Battle is primary; no per-case deep dive during this batch.",
            "At most one improvement candidate should be taken from each Battle.",
            "Unresolved cases may proceed to the next Battle.",
            "No candidate adoption or maturity promotion occurs automatically."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BATTLE_FIRST_BATCH "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
