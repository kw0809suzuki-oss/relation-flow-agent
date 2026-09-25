#!/usr/bin/env python3
"""External discriminator pair observer for seeds 8801/8806.

Captures daily first-observed World state (farm + market + town) for WR-02.
No candidate mutation, model call, or causal inference.
"""
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_external_discriminator_pair_v0_{SEED}_seat{SEAT}.json")
TARGET_DAYS=set(range(13))
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
      "unlocked_tiles":unlocked,"empty_tiles":empty,"productive_tiles":productive,
      "workers":workers,"productive_occupancy":productive/max(1,unlocked),
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
        market=obs.get("market",{}) or {}
        prices=market.get("prices",{}) or {}
        inventory=market.get("inventory",{}) or {}
        town=obs.get("town",{}) or {}
        daily[str(day)]={
          "hour":int(obs.get("hour",0) or 0),
          "self":body(farms[SEAT]),
          "opponent":body(farms[1-SEAT]),
          "market":{
            "prices":{p:float(prices.get(p,0) or 0) for p in PRODUCTS},
            "inventory":{p:float(inventory.get(p,0) or 0) for p in PRODUCTS},
          },
          "town":{"unlocked_shops":sorted(str(x) for x in (town.get("unlocked_shops",[]) or []))}
        }

    OUT.write_text(json.dumps({
      "schema":"kaggriculture.phase-a-external-discriminator-pair.v0",
      "seed":SEED,"seat":SEAT,"days":daily,
      "boundary":[
        "WR-02 only.",
        "Daily first-observed external World state only.",
        "No candidate outcome or causal interpretation is included."
      ]
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
