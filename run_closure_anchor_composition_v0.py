#!/usr/bin/env python3
"""Closure Anchor Composition v0.

A: Current G17 baseline
B: D12 Closure anchor
C: D14 Closure anchor
D: D14 Closure + S12 seed restraint

Because D14 already suppresses expansion from Day14 onward, D differs from C
only by suppressing BUY_SEED on Day12-13. This is a minimal composition test:
does a known-positive seed restraint preserve or amplify the Closure anchor?

No auto-adoption.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"closure_anchor_composition_v0_{SEED}.json")

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

def play(mode):
    configure()
    events=[]
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    def agent(obs):
        actions=native.agent(obs)
        if mode=="BASE" or not isinstance(actions,dict):
            return actions
        day=int(obs.get("day",0) or 0)
        market=list(actions.get("market",[]) or [])
        def suppress(a):
            if mode=="D12":
                return day>=12 and is_expansion(a)
            if mode=="D14":
                return day>=14 and is_expansion(a)
            if mode=="D14_S12":
                if day>=14 and is_expansion(a):
                    return True
                return day in (12,13) and isinstance(a,(list,tuple)) and a and a[0]=="BUY_SEED"
            return False
        removed=[copy.deepcopy(a) for a in market if suppress(a)]
        if not removed:
            return actions
        revised=copy.deepcopy(actions)
        revised["market"]=[a for a in market if not suppress(a)]
        events.append({"day":day,"removed":removed})
        return revised
    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],
            "event_count":len(events),"event_days":sorted({e["day"] for e in events})}

def main():
    b=play("BASE")
    out={}
    for mode in ("D12","D14","D14_S12"):
        r=play(mode)
        out[mode]={**r,"diff_self_vs_base":r["self"]-b["self"],"diff_margin_vs_base":r["margin"]-b["margin"]}
    out["D14_S12"]["diff_self_vs_D14"]=out["D14_S12"]["self"]-out["D14"]["self"]
    out["D14_S12"]["diff_margin_vs_D14"]=out["D14_S12"]["margin"]-out["D14"]["margin"]
    payload={
      "schema":"kaggriculture.closure-anchor-composition.v0",
      "seed":SEED,"seat":SEAT,"baseline":b,"variants":out,
      "boundary":[
        "Closure is the Anchor.",
        "D14_S12 differs from D14 only by BUY_SEED suppression on Day12-13.",
        "Primary composition read is D14_S12 versus D14.",
        "No causal claim and no auto-adoption."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CLOSURE_ANCHOR_COMPOSITION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
