#!/usr/bin/env python3
"""Closure + HIRE Preservation Ablation v0.

Baseline:
- Current Combat Model, including adopted Day14 coarse expansion closure.
- HIRE remains native/preserved.

Variant:
- Same Current Combat Model.
- From day 14 onward only HIRE orders are removed.

Purpose:
Test whether preserving HIRE inside the adopted Closure composition contributes
to flow/terminal performance. This is an ablation, not a new positive rule.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"closure_hire_preservation_ablation_v0_{SEED}.json")
START_DAY=14

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
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "hands":len(me.get("hands",[]) or []),
        "land":len(me.get("unlocked_quadrants",[]) or []),
    }

def play(suppress_hire):
    configure()
    events=[]
    daily={}
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        daily[int(obs.get("day",0) or 0)]=snap(obs)
        actions=current.agent(obs)
        if not suppress_hire or not isinstance(actions,dict):
            return actions
        day=int(obs.get("day",0) or 0)
        if day < START_DAY:
            return actions
        market=list(actions.get("market",[]) or [])
        removed=[copy.deepcopy(a) for a in market if isinstance(a,(list,tuple)) and a and a[0]=="HIRE"]
        if not removed:
            return actions
        revised=copy.deepcopy(actions)
        revised["market"]=[a for a in market if not (isinstance(a,(list,tuple)) and a and a[0]=="HIRE")]
        events.append({
            "day":day,
            "removed":removed,
            "money":obs["farms"][obs["player"]].get("money"),
            "hands":len(obs["farms"][obs["player"]].get("hands",[]) or []),
        })
        return revised

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "activation_count":len(events),
        "activation_days":sorted({e["day"] for e in events}),
        "events":events,
        "days":{str(d):daily.get(d) for d in (13,14,16,18,20,24,29) if d in daily},
    }

def main():
    baseline=play(False)
    ablated=play(True)
    b=baseline["terminal"]
    a=ablated["terminal"]

    flow={}
    for d in ("14","18","24","29"):
        bs=baseline["days"].get(d)
        av=ablated["days"].get(d)
        flow[d]=None if not bs or not av else {
            "hands_diff":av["hands"]-bs["hands"],
            "money_diff":av["money"]-bs["money"],
            "land_diff":av["land"]-bs["land"],
        }

    payload={
        "schema":"kaggriculture.composition.closure-hire-preservation-ablation.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":baseline,
        "hire_suppressed_after_d14":ablated,
        "reachability":{
            "activation_count":ablated["activation_count"],
            "activation_days":ablated["activation_days"],
            "reached":ablated["activation_count"]>0,
        },
        "flow_change":flow,
        "terminal_effect":{
            "self_diff":a["self"]-b["self"],
            "margin_diff":a["margin"]-b["margin"],
            "baseline_win":b["win"],
            "ablated_win":a["win"],
            "direction":"improved" if a["self"]>b["self"] else "worsened" if a["self"]<b["self"] else "equal",
        },
        "boundary":[
            "Baseline is the Current Combat Model with adopted Day14 expansion closure and native HIRE preserved.",
            "Variant changes only HIRE: from day14 onward submitted HIRE orders are removed.",
            "LAND/SEED/ANIMAL closure behavior remains the same through the Current Combat Model.",
            "No early-harvest override or other switch behavior is added.",
            "Fresh paired seed/seat comparison; no auto-adoption.",
        ],
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CLOSURE_HIRE_PRESERVATION_ABLATION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
