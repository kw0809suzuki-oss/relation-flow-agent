#!/usr/bin/env python3
"""SB-01 Day0 aligned transition export preflight v1.

Important env.steps alignment:
- action stored on row i is the action that produced observation on row i
- therefore pre-State is row i-1, Action is row i.action, post-State is row i

Exports exactly the 24 transitions whose pre-State is Day0, including the
closing Day0 hour23 -> Day1 hour0 transition.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ.get("BATTLE_SEED","7001"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"sb01_day0_aligned_transitions_{SEED}.json")


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

    steps=getattr(env,"steps",[]) or []
    transitions=[]
    for i in range(1,len(steps)):
        prev=steps[i-1]; cur=steps[i]
        if not isinstance(prev,(list,tuple)) or not isinstance(cur,(list,tuple)) or len(prev)<2 or len(cur)<2:
            continue
        pre0=plain(getv(prev[0],"observation"))
        post0=plain(getv(cur[0],"observation"))
        if not isinstance(pre0,dict) or not isinstance(post0,dict):
            continue
        if int(pre0.get("day",0) or 0)!=0:
            if transitions:
                break
            continue
        row={
            "transition_index":len(transitions),
            "from":{"day":int(pre0.get("day",0) or 0),"hour":int(pre0.get("hour",0) or 0),"step":int(pre0.get("step",0) or 0)},
            "to":{"day":int(post0.get("day",0) or 0),"hour":int(post0.get("hour",0) or 0),"step":int(post0.get("step",0) or 0)},
        }
        for s in (0,1):
            row[f"seat{s}"]={
                "pre_observation":plain(getv(prev[s],"observation")),
                "action":plain(getv(cur[s],"action")),
                "post_observation":plain(getv(cur[s],"observation")),
            }
        transitions.append(row)

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.sb01.day0-aligned-transitions.preflight.v1",
        "policy_mutated":False,
        "seed":SEED,
        "seat":SEAT,
        "transitions":transitions,
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "audit":{
            "transition_count":len(transitions),
            "first_from":transitions[0]["from"] if transitions else None,
            "first_to":transitions[0]["to"] if transitions else None,
            "last_from":transitions[-1]["from"] if transitions else None,
            "last_to":transitions[-1]["to"] if transitions else None,
        },
        "boundary":[
            "pre-State/action/post-State are explicitly aligned from adjacent env.steps rows.",
            "Exactly transitions with Day0 pre-State are exported.",
            "No policy or Action path is modified."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")

    last=transitions[-1] if transitions else {}
    print("SB01_DAY0_ALIGNED_PREFLIGHT "+json.dumps({
        "audit":payload["audit"],
        "first_action_seat0":transitions[0]["seat0"]["action"] if transitions else None,
        "first_pre_money_seat0":transitions[0]["seat0"]["pre_observation"]["farms"][0]["money"] if transitions else None,
        "first_post_money_seat0":transitions[0]["seat0"]["post_observation"]["farms"][0]["money"] if transitions else None,
        "last_action_seat0":last.get("seat0",{}).get("action"),
        "last_action_seat1":last.get("seat1",{}).get("action"),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
