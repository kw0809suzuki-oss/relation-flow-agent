#!/usr/bin/env python3
"""High-Leverage Closure Robustness v0.

Fresh50 A/B/C:
- baseline current G17
- D12 coarse expansion closure
- D14 coarse expansion closure

Same seed/seat/opponent/runtime config.
Purpose: Magnitude / Direction / Robustness only.
No causal claim. No auto-adoption.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"high_leverage_closure_robustness_v0_{SEED}.json")

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
    players=[OPPONENT,OPPONENT]
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
    out={}
    for name,day in (("D12",12),("D14",14)):
        r=play(day)
        out[name]={
            **r,
            "diff_self":r["self"]-baseline["self"],
            "diff_margin":r["margin"]-baseline["margin"],
            "direction_self":"improved" if r["self"]>baseline["self"] else "worsened" if r["self"]<baseline["self"] else "equal",
            "direction_margin":"improved" if r["margin"]>baseline["margin"] else "worsened" if r["margin"]<baseline["margin"] else "equal",
        }
    payload={
        "schema":"kaggriculture.high-leverage.closure-robustness.v0",
        "seed":SEED,"seat":SEAT,"baseline":baseline,"variants":out,
        "run_id":os.environ.get("GITHUB_RUN_ID"),"commit":os.environ.get("GITHUB_SHA"),
        "boundary":[
            "Same native G17 baseline, seed, seat, opponent and runtime configuration.",
            "D12/D14 only; coarse expansion closure.",
            "Magnitude / Direction / Robustness screening only.",
            "No causal claim and no auto-adoption."
        ],
        "artifact":f"high-leverage-closure-robustness-v0-{SEED}"
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HIGH_LEVERAGE_CLOSURE_ROBUSTNESS_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
