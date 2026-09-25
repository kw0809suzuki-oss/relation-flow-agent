#!/usr/bin/env python3
"""Pair probe: locate the first World-state divergence caused by Surface First.

Runs Active WR-02 and Surface First on the same seed/seat for 8801 or 8806.
Captures daily first-observed self/opponent farm state plus shared market/town.
No causal conclusion is encoded.
"""
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active
import phase_a_takeoff_variants_v0 as variants

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_surface_pair_flow_v0_{SEED}_seat{SEAT}.json")
PRODUCTS=("WHEAT","STRAWBERRY","MELON","MILK","WOOL","EGG","FERTILIZER")
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

def farm_body(farm):
    productive=0; unlocked=0; empty=0
    crops=Counter(); animals=Counter()
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if t!="LOCKED": unlocked+=1
            if t is None: empty+=1
            elif isinstance(t,dict):
                if t.get("kind")=="PLANT" and t.get("crop"):
                    productive+=1; crops[str(t["crop"])]+=1
                elif t.get("animal"):
                    productive+=1; animals[str(t["animal"])]+=1
    workers=1+len(farm.get("hands",[]) or [])
    return {
      "cash":float(farm.get("money",0) or 0),
      "quadrants":len(farm.get("unlocked_quadrants",[]) or []),
      "unlocked_tiles":unlocked,"empty_tiles":empty,"productive_tiles":productive,
      "workers":workers,
      "crops":{c:int(crops.get(c,0)) for c in CROPS},
      "animals":{a:int(animals.get(a,0)) for a in ANIMALS},
    }

def capture(env):
    daily={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<=SEAT: continue
        obs=plain(getv(step[SEAT],"observation"))
        if not isinstance(obs,dict): continue
        day=int(obs.get("day",0) or 0)
        if day>12 or str(day) in daily: continue
        farms=obs.get("farms",[]) or []
        if len(farms)<2: continue
        market=obs.get("market",{}) or {}; town=obs.get("town",{}) or {}
        prices=market.get("prices",{}) or {}; inv=market.get("inventory",{}) or {}
        daily[str(day)]={
          "hour":int(obs.get("hour",0) or 0),
          "self":farm_body(farms[SEAT]),
          "opponent":farm_body(farms[1-SEAT]),
          "market":{
            "prices":{p:float(prices.get(p,0) or 0) for p in PRODUCTS},
            "inventory":{p:float(inv.get(p,0) or 0) for p in PRODUCTS},
          },
          "town":{"unlocked_shops":sorted(str(x) for x in (town.get("unlocked_shops",[]) or []))}
        }
    return daily

def play(mode):
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    if mode=="active":
        active.reset_telemetry(); players[SEAT]=active.agent
    else:
        variants.set_mode("surface_first"); variants.reset_telemetry(); players[SEAT]=variants.agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    telemetry=active.get_telemetry() if mode=="active" else variants.get_telemetry()
    return {
      "terminal_self":rewards[SEAT],
      "daily":capture(env),
      "telemetry":telemetry,
    }

def main():
    active_result=play("active")
    surface_result=play("surface")
    OUT.write_text(json.dumps({
      "schema":"kaggriculture.phase-a-surface-pair-flow.v0",
      "seed":SEED,"seat":SEAT,
      "active":active_result,
      "surface":surface_result,
      "delta_terminal_self":surface_result["terminal_self"]-active_result["terminal_self"],
      "boundary":[
        "Same seed and seat for Active WR-02 and Surface First.",
        "The probe locates the first observed downstream divergence after Surface intervention.",
        "It does not assign causality to shop identity or market price."
      ]
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
