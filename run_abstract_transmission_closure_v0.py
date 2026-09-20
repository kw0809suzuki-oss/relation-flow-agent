#!/usr/bin/env python3
"""Abstract Transmission Phase v0.

Question:
If we pass only the abstract meaning CLOSURE to the current model,
does its existing behavior change in a terminal-useful direction?

No action is directly suppressed, forced, or rewritten.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"abstract_transmission_closure_v0_{SEED}.json")

def configure(closure_day=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    if closure_day is None:
        os.environ.pop("OUTER_MEANING_CLOSURE_DAY",None)
    else:
        os.environ["OUTER_MEANING_CLOSURE_DAY"]=str(closure_day)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(closure_day=None):
    configure(closure_day)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    meaning_calls=0
    def agent(obs):
        nonlocal meaning_calls
        if closure_day is not None and int(obs.get("day",0) or 0)>=closure_day:
            meaning_calls+=1
        return combat.agent(obs)
    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    trace=combat.get_trace()
    last_integration=((trace.get("observe",{}) or {}).get("body",{}) or {})
    return {
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "meaning_calls":meaning_calls,
    }

def main():
    b=play(None)
    variants={}
    for name,day in (("C12",12),("C14",14)):
        r=play(day)
        variants[name]={
            **r,
            "diff_self":r["self"]-b["self"],
            "diff_margin":r["margin"]-b["margin"],
        }
    payload={
        "schema":"kaggriculture.abstract-transmission.closure.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":b,
        "variants":variants,
        "abstraction":{
            "phase":"CLOSURE",
            "priority":"RECOVER_VALUE",
            "risk":"LONG_PAYBACK",
            "action_instruction":None,
            "strategy_instruction":None,
        },
        "boundary":[
            "Public state only determines when the abstraction is present.",
            "No BUY/SELL/HIRE/HARVEST action is directly suppressed or forced.",
            "The abstraction enters through the existing field/context integration path.",
            "This is a transmission test, not an adoption."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ABSTRACT_TRANSMISSION_CLOSURE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
