#!/usr/bin/env python3
"""Observation-only Day0 crop Gate trace for Strong Origin v2 Body-only v0.

Seed/seat fixed by env. Candidate action is returned unchanged.
Records only pre-State and existing strong_origin_body trace for Day0.
"""
import copy, json, os
from pathlib import Path

from kaggle_environments import make
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as candidate
import strong_origin_body as body

SEED=int(os.environ.get("BATTLE_SEED","7351"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"strong_origin_v2_day0_crop_gate_trace_v0_{SEED}.json")
records=[]

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):
        return v
    if isinstance(v,dict):
        return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):
        return [plain(x) for x in v]
    if hasattr(v,"items"):
        try: return {str(k):plain(x) for k,x in v.items()}
        except Exception: pass
    if hasattr(v,"tolist"):
        try: return plain(v.tolist())
        except Exception: pass
    if hasattr(v,"item"):
        try: return plain(v.item())
        except Exception: pass
    if hasattr(v,"__dict__"):
        try: return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception: pass
    return str(v)

def farm_view(obs):
    farms=obs.get("farms",[]) or []
    me=farms[SEAT] if len(farms)>SEAT else {}
    private=obs.get("private",{}) or {}
    return {
        "money": me.get("money"),
        "farmer": plain(me.get("farmer")),
        "hands": plain(me.get("hands",[])),
        "seeds": plain(private.get("seeds",{})),
        "tiles": plain(me.get("tiles",[])),
    }

def observed_agent(obs):
    action=candidate.agent(obs)
    p=plain(obs)
    day=int(p.get("day",0) or 0)
    if day==0:
        records.append({
            "turn_index":len(records),
            "day":day,
            "hour":int(p.get("hour",0) or 0),
            "pre":farm_view(p),
            "action":plain(copy.deepcopy(action)),
            "trace":plain(copy.deepcopy(body.get_last_trace())),
        })
    return action

def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    candidate.reset_telemetry()

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=observed_agent
    env.run(players)

    payload={
        "schema":"kaggriculture.strong-origin-v2.day0-crop-gate-trace.v0",
        "seed":SEED,
        "seat":SEAT,
        "terminal":{
            "self":float(env.state[SEAT].reward),
            "opponent":float(env.state[1-SEAT].reward),
        },
        "records":records,
        "boundary":[
            "Observation only: candidate actions are returned unchanged.",
            "Only Day0 pre-State and existing strong_origin_body trace are recorded.",
            "No post-State causal alignment is inferred in v0.",
            "Unknown remains Unknown."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    compact=[]
    for r in records:
        tr=r.get("trace",{})
        internal=tr.get("internal",{})
        final=tr.get("final_action",{})
        compact.append({
            "hour":r["hour"],
            "pre_seeds":r["pre"].get("seeds",{}),
            "targets":internal.get("targets",{}),
            "farmer":final.get("farmer"),
            "hands":final.get("hands",[]),
            "market":final.get("market",[]),
        })
    print("DAY0_CROP_GATE_TRACE "+json.dumps({
        "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],"turns":compact
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
