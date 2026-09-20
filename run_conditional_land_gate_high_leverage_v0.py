#!/usr/bin/env python3
"""High-Leverage conditional LAND gate v0.

At the first native BUY_LAND, suppress it only when observable opponent money <= 430.
This is a coarse separator probe derived from the 7101-7110 outer prestate sample.
No causal claim; no auto-adoption.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"conditional_land_gate_v0_{SEED}.json")
THRESHOLD=430.0

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()

def play(use_gate):
    configure()
    seen=False
    activated=False
    pre=None
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        nonlocal seen,activated,pre
        actions=native.agent(obs)
        if seen or not isinstance(actions,dict):
            return actions
        market=list(actions.get("market",[]) or [])
        hit=any(isinstance(a,(list,tuple)) and a and a[0]=="BUY_LAND" for a in market)
        if not hit:
            return actions
        seen=True
        p=int(obs["player"])
        me=obs["farms"][p]; opp=obs["farms"][1-p]
        pre={
            "day":int(obs.get("day",0) or 0),
            "self_money":float(me.get("money",0) or 0),
            "opponent_money":float(opp.get("money",0) or 0),
        }
        if not use_gate or pre["opponent_money"]>THRESHOLD:
            return actions
        revised=copy.deepcopy(actions)
        revised["market"]=[a for a in market if not (isinstance(a,(list,tuple)) and a and a[0]=="BUY_LAND")]
        activated=True
        return revised

    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "activated":activated,
        "pre":pre,
    }

def main():
    b=play(False)
    c=play(True)
    payload={
        "schema":"kaggriculture.high-leverage.conditional-land-gate.v0",
        "seed":SEED,"seat":SEAT,
        "threshold_opponent_money":THRESHOLD,
        "baseline":b,"candidate":c,
        "self_diff":c["self"]-b["self"],
        "margin_diff":c["margin"]-b["margin"],
        "direction":"improved" if c["self"]>b["self"] else "worsened" if c["self"]<b["self"] else "equal",
        "boundary":[
            "Outer observable gate only.",
            "Threshold is a coarse separator probe from prior sample, not a causal law.",
            "No rescue conditions and no auto-adoption."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CONDITIONAL_LAND_GATE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
