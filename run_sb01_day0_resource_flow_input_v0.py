#!/usr/bin/env python3
"""SB-01 Day0 Resource Flow raw export v0.

Exact SB-01 benchmark runtime. No intervention.
After env.run(), export all Day0 retained observations + actions and first Day1
observation for both seats so acquisition -> conversion can be derived mechanically.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"sb01_day0_resource_flow_input_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception: pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception: pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception: pass
    if hasattr(v,"__dict__"):
        try:return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception: pass
    return str(v)


def getv(s,k,default=None):
    if isinstance(s,dict): return s.get(k,default)
    try:return getattr(s,k)
    except Exception:return default


def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)

    day0=[]
    day1_first={"0":None,"1":None}
    for idx,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        obs=[plain(getv(step[s],"observation")) for s in (0,1)]
        acts=[plain(getv(step[s],"action")) for s in (0,1)]
        if not all(isinstance(o,dict) for o in obs): continue
        day=int(obs[0].get("day",0) or 0)
        hour=int(obs[0].get("hour",0) or 0)
        if day==0:
            day0.append({
                "step_index":idx,
                "hour":hour,
                "seat0":{"observation":obs[0],"action":acts[0]},
                "seat1":{"observation":obs[1],"action":acts[1]},
            })
        elif day==1:
            for s in (0,1):
                if day1_first[str(s)] is None:
                    day1_first[str(s)]={"step_index":idx,"observation":obs[s]}
            if all(day1_first[str(s)] is not None for s in (0,1)):
                break

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.sb01.day0-resource-flow-input.v0",
        "policy_mutated":False,
        "seed":SEED,
        "seat":SEAT,
        "benchmark":"strength_benchmark_v0",
        "day0_steps":day0,
        "day1_first":day1_first,
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "audit":{
            "day0_rows":len(day0),
            "day0_hours":[r["hour"] for r in day0],
            "day1_first_present":{s:day1_first[s] is not None for s in ("0","1")},
        },
        "boundary":[
            "Exact SB-01 policy/runtime is reused.",
            "No Candidate, observer wrapper, threshold, or Action mutation.",
            "Retained State and Action are read only after env.run().",
            "This is raw input for acquisition/conversion accounting."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print("SB01_DAY0_RESOURCE_FLOW_INPUT "+json.dumps({
        "seed":SEED,"seat":SEAT,"audit":payload["audit"],"terminal":payload["terminal"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
