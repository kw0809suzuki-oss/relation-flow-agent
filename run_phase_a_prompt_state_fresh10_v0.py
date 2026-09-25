#!/usr/bin/env python3
"""Fresh10 blind state capture for Phase A instruction comparison.

Capture WR-02 World State only. No Surface / Throughput / Engine candidate is
run here, so terminal-winning direction is not available at prediction time.
"""
import json,os
from collections import Counter
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_prompt_state_fresh10_v0_{SEED}_seat{SEAT}.json")
TARGET_DAYS=(4,8)
CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("GOOSE","COW","SHEEP")
PRODUCTS=("WHEAT","STRAWBERRY","MELON","MILK","WOOL","EGG","FERTILIZER")

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
      "quadrants":len(farm.get("unlocked_quadrants",[]) or []),
      "unlocked_tiles":unlocked,
      "empty_tiles":empty,
      "productive_tiles":productive,
      "workers":workers,
      "productive_occupancy":productive/max(1,unlocked),
      "productive_per_worker":productive/max(1,workers),
      "crop_count":{c:int(crop.get(c,0)) for c in CROPS},
      "animal_count":{a:int(animal.get(a,0)) for a in ANIMALS},
    }

def world(obs,seat):
    farms=obs.get("farms",[]) or []
    market=obs.get("market",{}) or {}
    prices=market.get("prices",{}) or {}
    inventory=market.get("inventory",{}) or {}
    town=obs.get("town",{}) or {}
    return {
      "day":int(obs.get("day",0) or 0),
      "hour":int(obs.get("hour",0) or 0),
      "self":body(farms[seat]),
      "opponent":body(farms[1-seat]),
      "market":{
        "prices":{p:float(prices.get(p,0) or 0) for p in PRODUCTS},
        "inventory":{p:float(inventory.get(p,0) or 0) for p in PRODUCTS},
      },
      "town":{"unlocked_shops":sorted(str(x) for x in (town.get("unlocked_shops",[]) or []))},
    }

def main():
    configure();active.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=active.agent
    env.run(players)
    checkpoints={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<=SEAT:continue
        obs=plain(getv(step[SEAT],"observation"))
        if not isinstance(obs,dict):continue
        d=int(obs.get("day",0) or 0)
        if d in TARGET_DAYS and str(d) not in checkpoints:
            checkpoints[str(d)]=world(obs,SEAT)
    payload={
      "schema":"kaggriculture.phase-a-prompt-state.fresh10.v0",
      "seed":SEED,"seat":SEAT,"checkpoints":checkpoints,
      "boundary":[
        "WR-02 World State only.",
        "No candidate direction is run or scored in this capture.",
        "Prediction must be committed before the four-arm Battle is run."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PROMPT_STATE "+json.dumps({"seed":SEED,"seat":SEAT,"checkpoints":checkpoints},ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
