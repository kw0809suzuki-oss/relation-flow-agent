#!/usr/bin/env python3
"""Dual Closure Candidate cross-opponent v0.

Keep D12 and D14 as parallel unresolved candidates.
Test both against multiple opponents under identical fresh seeds/seat pattern.
No winner selection, no auto-adoption.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT_NAME=os.environ["OPPONENT_NAME"]
OPPONENT_PATH=os.environ["OPPONENT_PATH"]
OUT=Path(f"dual_closure_cross_opponent_v0_{OPPONENT_NAME}_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()

def is_expansion(a):
    if not isinstance(a,(list,tuple)) or not a:
        return False
    op=a[0]
    if op in ("BUY_LAND","BUY_SEED","BUY_ANIMAL"):
        return True
    return op=="BUY_PRODUCT" and len(a)>1 and a[1]=="COW"

def play(start_day=None):
    configure()
    acts=[]
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    def agent(obs):
        actions=native.agent(obs)
        if start_day is None or not isinstance(actions,dict):
            return actions
        day=int(obs.get("day",0) or 0)
        if day < start_day:
            return actions
        market=list(actions.get("market",[]) or [])
        removed=[copy.deepcopy(a) for a in market if is_expansion(a)]
        if not removed:
            return actions
        revised=copy.deepcopy(actions)
        revised["market"]=[a for a in market if not is_expansion(a)]
        acts.append({"day":day,"removed":removed})
        return revised
    players=[OPPONENT_PATH,OPPONENT_PATH]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "activation_count":len(acts),
        "activation_days":sorted({x["day"] for x in acts})
    }

def main():
    baseline=play(None)
    variants={}
    for name,day in (("D12",12),("D14",14)):
        r=play(day)
        variants[name]={
            **r,
            "diff_self":r["self"]-baseline["self"],
            "diff_margin":r["margin"]-baseline["margin"],
        }
    payload={
        "schema":"kaggriculture.dual-closure-cross-opponent.v0",
        "opponent":OPPONENT_NAME,
        "seed":SEED,"seat":SEAT,
        "baseline":baseline,"variants":variants,
        "boundary":[
            "D12 and D14 remain parallel unresolved candidates.",
            "Cross-opponent robustness test only.",
            "No ranking, merge, or adoption is performed automatically."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DUAL_CLOSURE_CROSS_OPPONENT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
