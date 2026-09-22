#!/usr/bin/env python3
"""Paired fresh10 Battle for Time-aware Liquidation Candidate v0."""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import time_aware_liquidation_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"time_aware_liquidation_v0_{SEED}.json")

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
    carried=sum(sum(int(inv.get(k,0) or 0) for k in ("WHEAT","MELON")) for inv in inventories if isinstance(inv,dict))
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "hands":len(me.get("hands",[]) or []),
        "shed_wheat":int(shed.get("WHEAT",0) or 0),
        "shed_melon":int(shed.get("MELON",0) or 0),
        "carried_crop":carried,
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
        "days":{str(d):daily.get(d) for d in (26,27,28,29) if d in daily},
        "telemetry":tele,
    }

def main():
    baseline=play("baseline")
    variant=play("candidate")
    b=baseline["terminal"]; v=variant["terminal"]
    tele=variant["telemetry"]
    flow={}
    for d in ("26","27","28","29"):
        bs=baseline["days"].get(d); vs=variant["days"].get(d)
        flow[d]=None if not bs or not vs else {
            "money_diff":vs["money"]-bs["money"],
            "shed_wheat_diff":vs["shed_wheat"]-bs["shed_wheat"],
            "shed_melon_diff":vs["shed_melon"]-bs["shed_melon"],
            "carried_crop_diff":vs["carried_crop"]-bs["carried_crop"],
        }

    payload={
        "schema":"kaggriculture.time-aware-liquidation.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":baseline,
        "candidate":variant,
        "reachability":{
            "eligible":tele.get("eligible",0),
            "overrides":tele.get("overrides",0),
            "reached":tele.get("overrides",0)>0,
            "event_days":sorted({e["day"] for e in tele.get("events",[])}),
        },
        "flow_change":flow,
        "terminal_effect":{
            "self_diff":v["self"]-b["self"],
            "margin_diff":v["margin"]-b["margin"],
            "baseline_win":b["win"],
            "candidate_win":v["win"],
            "direction":"improved" if v["self"]>b["self"] else "worsened" if v["self"]<b["self"] else "equal",
        },
        "boundary":[
            "Baseline is Current Combat Model: adopted Day14 expansion closure with HIRE preserved.",
            "Candidate changes only harvest timing for harvestable WHEAT/MELON when native max-yield wait_days >= remaining_days.",
            "Native SELL behavior is untouched.",
            "No price predictor, no transport predictor, no added reserve, no post-result rescue condition.",
            "Fresh paired seed/seat comparison; no auto-adoption."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TIME_AWARE_LIQUIDATION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
