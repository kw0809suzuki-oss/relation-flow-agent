#!/usr/bin/env python3
"""Phase A outer-State label audit v0.

Replays the current Active Model (WR-02) on the same 8401-8420 cases used by
the three-pattern Phase A Battle. Captures only self-visible outer State at
Day0 / Day4 / Day8. No candidate mutation.

The aggregate step later joins these States to the already-observed terminal
winner among HOLD / Surface / Throughput / Engine.
"""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_outer_state_v0_{SEED}_seat{SEAT}.json")
TARGET_DAYS=(0,4,8)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception:pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict): return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def outer(obs,seat):
    farms=obs.get("farms",[]) or []
    farm=farms[seat]
    productive=0; unlocked=0; empty=0; plants=0; animals=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if t!="LOCKED":
                unlocked+=1
            if t is None:
                empty+=1
            elif isinstance(t,dict):
                if t.get("kind")=="PLANT":
                    productive+=1;plants+=1
                elif t.get("animal"):
                    productive+=1;animals+=1
    workers=1+len(farm.get("hands",[]) or [])
    private=obs.get("private",{}) or {}
    seeds=private.get("seeds",{}) or {}
    return {
      "day":int(obs.get("day",0) or 0),
      "hour":int(obs.get("hour",0) or 0),
      "cash":float(farm.get("money",0) or 0),
      "quadrants":len(farm.get("unlocked_quadrants",[]) or []),
      "unlocked_tiles":unlocked,
      "empty_tiles":empty,
      "productive_tiles":productive,
      "plants":plants,
      "animals":animals,
      "workers":workers,
      "productive_occupancy":productive/max(1,unlocked),
      "productive_per_worker":productive/max(1,workers),
      "seed_total":sum(int(v or 0) for v in seeds.values()),
      "seed_by_crop":{k:int(v or 0) for k,v in seeds.items()},
    }


def main():
    configure();active.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=active.agent
    env.run(players)

    checkpoints={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<=SEAT: continue
        obs=plain(getv(step[SEAT],"observation"))
        if not isinstance(obs,dict): continue
        d=int(obs.get("day",0) or 0)
        if d in TARGET_DAYS and str(d) not in checkpoints:
            checkpoints[str(d)]=outer(obs,SEAT)

    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.phase-a-outer-state.v0",
      "seed":SEED,"seat":SEAT,
      "checkpoints":checkpoints,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "boundary":[
        "Current Active Model WR-02 only; no Phase A candidate mutation.",
        "Only self-visible outer State is captured.",
        "No opponent features, hidden trace, seed identity, terminal result, or future information is used as a State feature."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE_A_OUTER_STATE "+json.dumps({"seed":SEED,"seat":SEAT,"checkpoints":checkpoints},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
