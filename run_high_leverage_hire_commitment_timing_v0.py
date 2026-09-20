#!/usr/bin/env python3
"""High-Leverage Hire Commitment Timing v0.

Baseline Current G17 vs suppress HIRE from D12 / D18 / D24 onward.
Isolates labor commitment timing from Closure and harvest changes.
Same seed/seat/opponent/runtime config. Magnitude/Direction/Robustness only.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"high_leverage_hire_commitment_timing_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()

def play(start_day=None):
    configure()
    events=[]
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    def agent(obs):
        actions=native.agent(obs)
        if start_day is None or not isinstance(actions,dict):
            return actions
        day=int(obs.get("day",0) or 0)
        if day<start_day:
            return actions
        market=list(actions.get("market",[]) or [])
        removed=[copy.deepcopy(a) for a in market if isinstance(a,(list,tuple)) and a and a[0]=="HIRE"]
        if not removed:
            return actions
        revised=copy.deepcopy(actions)
        revised["market"]=[a for a in market if not (isinstance(a,(list,tuple)) and a and a[0]=="HIRE")]
        events.append({"day":day,"removed":removed})
        return revised
    players=[OPPONENT,OPPONENT]; players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],
            "event_count":len(events),"event_days":sorted({e["day"] for e in events})}

def main():
    b=play(None)
    variants={}
    for name,day in (("HIRE12",12),("HIRE18",18),("HIRE24",24)):
        r=play(day)
        variants[name]={**r,"diff_self":r["self"]-b["self"],"diff_margin":r["margin"]-b["margin"]}
    payload={
      "schema":"kaggriculture.high-leverage.hire-commitment-timing.v0",
      "seed":SEED,"seat":SEAT,"baseline":b,"variants":variants,
      "boundary":[
        "Only HIRE timing is changed; LAND/COW/SEED/harvest/sell remain native.",
        "Same native G17 baseline, seed, seat, opponent and runtime config.",
        "Magnitude / Direction / Robustness screening only.",
        "No causal claim and no auto-adoption."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HIGH_LEVERAGE_HIRE_COMMITMENT_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
