#!/usr/bin/env python3
"""Paired fresh10 Battle for Final-mile Liquidation Candidate v0."""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import final_mile_liquidation_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"final_mile_liquidation_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()

def snap(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    private=obs.get("private",{}) or {}
    shed=private.get("shed",{}) or {}
    inventories=private.get("inventories",[]) or []
    carried=sum(
        sum(int(inv.get(k,0) or 0) for k in ("WHEAT","STRAWBERRY","MELON"))
        for inv in inventories if isinstance(inv,dict)
    )
    shed_crop=sum(int(shed.get(k,0) or 0) for k in ("WHEAT","STRAWBERRY","MELON"))
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "carried_crop":carried,
        "shed_crop":shed_crop,
    }

def play(mode):
    configure()
    if mode=="candidate":
        candidate.reset_experiment()
    daily={}
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        daily[int(obs.get("day",0) or 0)]=snap(obs)
        return candidate.agent(obs) if mode=="candidate" else current.agent(obs)

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    tele=candidate.get_experiment_telemetry() if mode=="candidate" else {}
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "days":{str(d):daily.get(d) for d in (28,29) if d in daily},
        "telemetry":tele,
    }

def main():
    baseline=play("baseline")
    variant=play("candidate")
    b=baseline["terminal"]; v=variant["terminal"]
    tele=variant["telemetry"]
    b29=baseline["days"].get("29") or {}
    v29=variant["days"].get("29") or {}
    payload={
        "schema":"kaggriculture.final-mile-liquidation.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":baseline,
        "candidate":variant,
        "reachability":{
            "eligible":tele.get("eligible",0),
            "move_overrides":tele.get("move_overrides",0),
            "drop_overrides":tele.get("drop_overrides",0),
            "reached":bool(tele.get("move_overrides",0) or tele.get("drop_overrides",0)),
        },
        "flow_change":{
            "day29_money_diff":(v29.get("money",0)-b29.get("money",0)) if b29 and v29 else None,
            "day29_carried_crop_diff":(v29.get("carried_crop",0)-b29.get("carried_crop",0)) if b29 and v29 else None,
            "day29_shed_crop_diff":(v29.get("shed_crop",0)-b29.get("shed_crop",0)) if b29 and v29 else None,
        },
        "terminal_effect":{
            "self_diff":v["self"]-b["self"],
            "margin_diff":v["margin"]-b["margin"],
            "baseline_win":b["win"],
            "candidate_win":v["win"],
            "direction":"improved" if v["self"]>b["self"] else "worsened" if v["self"]<b["self"] else "equal",
        },
        "boundary":[
            "Baseline is Current Combat Model with D14 closure and HIRE preserved.",
            "Candidate changes only final-day routing for units carrying WHEAT/STRAWBERRY/MELON.",
            "Carrying units return to a shed-adjacent cell and DROP; native SELL remains untouched.",
            "Native HARVEST timing remains untouched.",
            "Fresh paired seed/seat comparison; no auto-adoption."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FINAL_MILE_LIQUIDATION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
