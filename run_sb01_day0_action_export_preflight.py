#!/usr/bin/env python3
"""SB-01 Day0 Action export preflight.

Runs the exact SB-01 benchmark case and, after env.run(), reads retained
Day-0 Action bundles from env.steps for both seats. No agent wrapper or policy change.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ.get("BATTLE_SEED","7001"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"sb01_day0_actions_{SEED}.json")


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

    rows=[]
    for i,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        obs0=plain(getv(step[0],"observation"))
        if not isinstance(obs0,dict): continue
        day=int(obs0.get("day",0) or 0)
        if day!=0: continue
        rows.append({
            "step_index":i,
            "day":day,
            "hour":int(obs0.get("hour",0) or 0),
            "seat0_action":plain(getv(step[0],"action")),
            "seat1_action":plain(getv(step[1],"action")),
        })

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.sb01.day0-actions.preflight.v0",
        "policy_mutated":False,
        "seed":SEED,
        "seat":SEAT,
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "day0_steps":rows,
        "audit":{
            "rows":len(rows),
            "non_null_action_rows_seat0":sum(r["seat0_action"] is not None for r in rows),
            "non_null_action_rows_seat1":sum(r["seat1_action"] is not None for r in rows),
        },
        "boundary":[
            "Actions are read after env.run() from retained environment steps.",
            "No agent wrapper or intervention is introduced.",
            "This is Action localization after temporal localization to Day 0->1."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    compact=[]
    for r in rows:
        if r["seat0_action"] is not None or r["seat1_action"] is not None:
            compact.append(r)
    print("SB01_DAY0_ACTION_PREFLIGHT "+json.dumps({"audit":payload["audit"],"actions":compact},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
