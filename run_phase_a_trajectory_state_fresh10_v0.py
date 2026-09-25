#!/usr/bin/env python3
"""Fresh10 WR-02 Phase A external trajectory capture, seeds 8801-8810.

Captures the first observable state for each day 0..12.
No candidate mutation, no model call, no direction judgment.
"""
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_trajectory_state_fresh10_v0_{SEED}_seat{SEAT}.json")
TARGET_DAYS=set(range(0,13))
CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("GOOSE","COW","SHEEP")

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

def body(farm):
    productive=0;unlocked=0;empty=0
    crop=Counter();animal=Counter()
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if t!="LOCKED": unlocked+=1
            if t is None: empty+=1
            elif isinstance(t,dict):
                if t.get("kind")=="PLANT" and t.get("crop"):
                    productive+=1;crop[str(t.get("crop"))]+=1
                elif t.get("animal"):
                    productive+=1;animal[str(t.get("animal"))]+=1
    workers=1+len(farm.get("hands",[]) or [])
    return {
      "cash":float(farm.get("money",0) or 0),
      "unlocked_tiles":unlocked,
      "empty_tiles":empty,
      "productive_tiles":productive,
      "workers":workers,
      "productive_occupancy":productive/max(1,unlocked),
      "productive_per_worker":productive/max(1,workers),
      "crop_count":{c:int(crop.get(c,0)) for c in CROPS},
      "animal_count":{a:int(animal.get(a,0)) for a in ANIMALS},
    }

def main():
    configure(); active.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]; players[SEAT]=active.agent
    env.run(players)

    daily={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<=SEAT: continue
        obs=plain(getv(step[SEAT],"observation"))
        if not isinstance(obs,dict): continue
        day=int(obs.get("day",0) or 0)
        if day not in TARGET_DAYS or str(day) in daily: continue
        farms=obs.get("farms",[]) or []
        if len(farms)<2: continue
        daily[str(day)]={
          "hour":int(obs.get("hour",0) or 0),
          "self":body(farms[SEAT]),
          "opponent":body(farms[1-SEAT]),
        }

    payload={
      "schema":"kaggriculture.phase-a-trajectory-state.fresh10.v0",
      "seed":SEED,"seat":SEAT,
      "days":daily,
      "boundary":[
        "Current Active Model WR-02 only.",
        "Only observable external state is captured.",
        "No direction judgment, candidate intervention, or terminal outcome label is included."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE_A_TRAJECTORY "+json.dumps({"seed":SEED,"seat":SEAT,"days":sorted(map(int,daily))},separators=(",",":")))

if __name__=="__main__": main()
