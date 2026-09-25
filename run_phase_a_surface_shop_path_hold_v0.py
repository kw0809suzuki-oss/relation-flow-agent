#!/usr/bin/env python3
"""Counterfactual pair probe: hold town shop path to the Active WR-02 path.

For each seed (8801 or 8806):
1) run Active WR-02 in the unmodified environment and record the realized town shop path,
2) run Surface First in the unmodified environment,
3) run Surface First again while forcing town.unlocked_shops after each end-of-day
   to the Active run's realized shop list for the next day.

This preserves Surface's farm/weed consequences but removes the candidate-induced
shop-path change as a downstream channel.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import kaggle_environments.envs.kaggriculture.kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active
import phase_a_takeoff_variants_v0 as variants

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_surface_shop_path_hold_v0_{SEED}_seat{SEAT}.json")

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

def shop_path(env):
    out={}
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<=SEAT: continue
        obs=plain(getv(step[SEAT],"observation"))
        if not isinstance(obs,dict): continue
        day=int(obs.get("day",0) or 0)
        if day in out: continue
        town=obs.get("town",{}) or {}
        out[day]=list(town.get("unlocked_shops",[]) or [])
    return out

def play_active():
    configure(); active.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]; players[SEAT]=active.agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return rewards[SEAT], shop_path(env)

def play_surface(force_path=None):
    configure(); variants.set_mode("surface_first"); variants.reset_telemetry()
    original=kg._end_of_day
    if force_path is not None:
        def forced_end_of_day(state, env, day):
            original(state,env,day)
            next_day=int(day)+1
            if next_day in force_path:
                state[0].observation.town["unlocked_shops"]=list(force_path[next_day])
        kg._end_of_day=forced_end_of_day
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        players=[basecfg.OPPONENT,basecfg.OPPONENT]; players[SEAT]=variants.agent
        env.run(players)
        rewards=[float(x.reward) for x in env.state]
        return rewards[SEAT], shop_path(env), variants.get_telemetry()
    finally:
        kg._end_of_day=original

def main():
    active_self,active_path=play_active()
    surface_self,surface_path,surface_tel=play_surface(None)
    held_self,held_path,held_tel=play_surface(active_path)
    payload={
      "schema":"kaggriculture.phase-a-surface-shop-path-hold.v0",
      "seed":SEED,"seat":SEAT,
      "terminal_self":{
        "active":active_self,
        "surface_original":surface_self,
        "surface_active_shop_path":held_self
      },
      "delta_vs_active":{
        "surface_original":surface_self-active_self,
        "surface_active_shop_path":held_self-active_self
      },
      "shop_paths":{
        "active":active_path,
        "surface_original":surface_path,
        "surface_active_shop_path":held_path
      },
      "changed_turns":{
        "surface_original":surface_tel.get("changed_turns"),
        "surface_active_shop_path":held_tel.get("changed_turns")
      },
      "boundary":[
        "The forced arm changes only the realized town unlocked_shops list after each end-of-day to match the Active run for that same seed.",
        "Surface First farm actions and weed consequences remain live.",
        "This tests whether removing the candidate-induced shop-path channel changes the terminal Surface effect.",
        "It does not isolate all market or RNG-mediated effects."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SURFACE_SHOP_PATH_HOLD "+json.dumps({
      "seed":SEED,
      "active":active_self,
      "surface_original":surface_self,
      "surface_active_shop_path":held_self,
      "delta_original":surface_self-active_self,
      "delta_held":held_self-active_self
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
