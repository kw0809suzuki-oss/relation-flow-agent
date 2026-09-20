#!/usr/bin/env python3
"""Day29 opening inventory vs liquidation observation for seed 6205.

No intervention. Distinguish accumulated-asset difference from liquidation-choice difference.
"""
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=6205
SEAT=0
DAY=29
OPPONENT_PATH=Path("opponents/seyamalam_v21.py")
OUT=Path("open_learning_day29_inventory_liquidation_v0.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def load_opponent():
    spec=importlib.util.spec_from_file_location("seyamalam_v21_runtime",OPPONENT_PATH)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn=getattr(mod,"agent",None)
    if not callable(fn):
        raise RuntimeError("opponent agent callable not found")
    return fn

def aggregate_private(private):
    totals=Counter()
    shed=(private.get("shed",{}) or {}) if isinstance(private,dict) else {}
    if isinstance(shed,dict):
        for k,v in shed.items():
            if isinstance(v,(int,float)): totals[str(k)]+=v
    inventories=(private.get("inventories",[]) or []) if isinstance(private,dict) else []
    for inv in inventories:
        if isinstance(inv,dict):
            for k,v in inv.items():
                if isinstance(v,(int,float)): totals[str(k)]+=v
    seeds=(private.get("seeds",{}) or {}) if isinstance(private,dict) else {}
    if isinstance(seeds,dict):
        for k,v in seeds.items():
            if isinstance(v,(int,float)): totals["SEED:"+str(k)]+=v
    return dict(totals)

def main():
    configure()
    opp=load_opponent()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    opening={0:None,1:None}
    sold={0:Counter(),1:Counter()}
    first_money={0:None,1:None}
    last_money_before={0:None,1:None}

    def wrap(player_index,fn):
        def agent(obs):
            day=int(obs.get("day",0) or 0)
            if day==DAY and opening[player_index] is None:
                opening[player_index]=aggregate_private(obs.get("private",{}) or {})
                first_money[player_index]=float(obs["farms"][player_index].get("money",0.0))
            action=fn(obs)
            if day==DAY:
                last_money_before[player_index]=float(obs["farms"][player_index].get("money",0.0))
                if isinstance(action,dict):
                    for a in list(action.get("market",[]) or []):
                        if isinstance(a,(list,tuple)) and len(a)>=3 and a[0]=="SELL":
                            sold[player_index][str(a[1])]+=a[2]
            return action
        return agent

    players=[None,None]
    players[SEAT]=wrap(SEAT,combat.agent)
    players[1-SEAT]=wrap(1-SEAT,opp)
    env.run(players)
    rewards=[float(x.reward) for x in env.state]

    payload={
        "schema":"kaggriculture.open-learning-day29-inventory-liquidation.v0",
        "case":{"seed":SEED,"self_seat":SEAT,"day":DAY},
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "players":{
            str(p):{
                "opening_inventory":opening[p],
                "sold_quantities":dict(sold[p]),
                "first_money":first_money[p],
                "last_money_before":last_money_before[p],
            } for p in (0,1)
        },
        "boundary":[
            "Observation only; no action is changed.",
            "Opening inventory is descriptive public-to-agent private state at first Day29 call.",
            "Sold quantity does not by itself establish profit or optimal liquidation."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPEN_LEARNING_DAY29_INVENTORY_LIQUIDATION "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
