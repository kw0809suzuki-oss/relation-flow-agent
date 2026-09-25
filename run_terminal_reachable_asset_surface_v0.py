#!/usr/bin/env python3
"""Terminal-Reachable Asset Surface v0.

Observation-only Day20 snapshot on the fixed five Battles.

Decomposes the existing Committed Production valuation basis into:
- READY: output units already at the public harvest/output boundary
- REACHABLE: committed units not READY now, but able to reach the public output
  boundary by the season terminal under the same explicit public-rule assumptions
  used by SB-01 Economic Layers
- NOT_REACHABLE: committed units counted by the existing valuation basis whose
  public harvest/output boundary lies after terminal

This probe stops at Asset -> Output boundary. It does not assume HARVEST ->
carried -> shed -> SELL -> Cash completion.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path

import kaggle_environments
from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"terminal_reachable_asset_surface_v0_{SEED}_seat{SEAT}.json")
ANCHOR_DAY=20
TERMINAL_DAY=econ.SEASON_DAYS


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):
        return v
    if isinstance(v,dict):
        return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):
        return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:
            return {str(k):plain(x) for k,x in v.items()}
        except Exception:
            pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict):
        return x.get(key,default)
    try:
        return getattr(x,key)
    except Exception:
        return default


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()


def split_crop(tile,day,prices):
    crop=tile["crop"]
    rule=econ.CROPS[crop]
    current=max(0,int(tile.get("yield_units",0) or 0))
    planted=int(tile.get("planted_day",day) or 0)
    first_day=planted+int(rule["first"])
    price=float(prices.get(crop,0) or 0)

    if bool(rule["ongoing"]):
        events=[]
        for n in range(int(rule["max_yield"])):
            d=planted+int(rule["first"])+n*int(rule["interval"])
            if day < d <= TERMINAL_DAY:
                events.append(d)
        potential=current+len(events)
        ready=current if day>=first_day else 0
        current_not_ready=current-ready
        reachable_current=current_not_ready if first_day<=TERMINAL_DAY else 0
        not_reachable_current=current_not_ready-reachable_current
        reachable_future=len(events)
        not_reachable_future=0
        return {
            "asset_type":crop,
            "asset_class":"crop",
            "product":crop,
            "origin_day":planted,
            "first_output_boundary_day":first_day,
            "next_public_output_boundary_day":(
                day if ready>0 else
                min(events) if events else
                first_day if current_not_ready>0 else None
            ),
            "current_held_units":current,
            "potential_units_same_basis":potential,
            "ready_units":ready,
            "reachable_units":reachable_current+reachable_future,
            "not_reachable_units":not_reachable_current+not_reachable_future,
            "price":price,
        }

    # Non-ongoing crop: same potential basis as econ._nonongoing_crop_remaining.
    window_start=(int(rule["max_day"])+1)//2
    first_water=max(day,planted+window_start)
    last_water=min(TERMINAL_DAY-1,planted+int(rule["max_day"]))
    opportunities=max(0,last_water-first_water+1)
    potential=min(int(rule["max_yield"]),current+opportunities)
    future_units=max(0,potential-current)

    ready=current if day>=first_day else 0
    current_not_ready=current-ready

    if first_day<=TERMINAL_DAY:
        reachable_current=current_not_ready
        not_reachable_current=0
        reachable_future=future_units
        not_reachable_future=0
    else:
        reachable_current=0
        not_reachable_current=current_not_ready
        reachable_future=0
        not_reachable_future=future_units

    return {
        "asset_type":crop,
        "asset_class":"crop",
        "product":crop,
        "origin_day":planted,
        "first_output_boundary_day":first_day,
        "next_public_output_boundary_day":(
            day if ready>0 else first_day if potential>0 else None
        ),
        "current_held_units":current,
        "remaining_water_opportunities_same_basis":opportunities,
        "potential_units_same_basis":potential,
        "ready_units":ready,
        "reachable_units":reachable_current+reachable_future,
        "not_reachable_units":not_reachable_current+not_reachable_future,
        "price":price,
    }


def split_animal(tile,day,prices):
    animal=tile["animal"]
    rule=econ.ANIMALS[animal]
    current=max(0,int(tile.get("yield_units",0) or 0))
    placed=int(tile.get("placed_day",day) or 0)
    first_day=placed+int(rule["first"])
    product=rule["product"]
    price=float(prices.get(product,0) or 0)

    events=[]
    d=first_day
    while d<=TERMINAL_DAY:
        if d>day:
            events.append(d)
        d+=int(rule["interval"])

    potential=current+len(events)
    ready=current if day>=first_day else 0
    current_not_ready=current-ready
    reachable_current=current_not_ready if first_day<=TERMINAL_DAY else 0
    not_reachable_current=current_not_ready-reachable_current

    return {
        "asset_type":animal,
        "asset_class":"animal",
        "product":product,
        "origin_day":placed,
        "first_output_boundary_day":first_day,
        "next_public_output_boundary_day":(
            day if ready>0 else min(events) if events else first_day if current_not_ready>0 else None
        ),
        "current_held_units":current,
        "potential_units_same_basis":potential,
        "ready_units":ready,
        "reachable_units":reachable_current+len(events),
        "not_reachable_units":not_reachable_current,
        "price":price,
    }


def classify_side(obs):
    player=int(obs["player"])
    farm=obs["farms"][player]
    prices=(obs.get("market",{}) or {}).get("prices",{}) or {}
    day=int(obs.get("day",0) or 0)
    rows=[]

    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,tile in enumerate(row or []):
            if not isinstance(tile,dict):
                continue
            z=None
            if tile.get("kind")=="PLANT" and tile.get("crop") in econ.CROPS:
                z=split_crop(tile,day,prices)
            elif tile.get("animal") in econ.ANIMALS:
                z=split_animal(tile,day,prices)
            if z is None:
                continue
            z["x"]=x;z["y"]=y
            for k in ("ready","reachable","not_reachable"):
                z[f"{k}_mark"]=z[f"{k}_units"]*z["price"]
            z["potential_mark_same_basis"]=z["potential_units_same_basis"]*z["price"]
            z["decomposition_error"]=z["potential_mark_same_basis"]-(
                z["ready_mark"]+z["reachable_mark"]+z["not_reachable_mark"]
            )
            rows.append(z)

    sums={
        "ready_mark":sum(z["ready_mark"] for z in rows),
        "reachable_mark":sum(z["reachable_mark"] for z in rows),
        "not_reachable_mark":sum(z["not_reachable_mark"] for z in rows),
        "committed_mark_reconstructed":sum(z["potential_mark_same_basis"] for z in rows),
    }
    econ_side=econ.derive_side(obs)
    expected=float(econ_side["committed_production"]["same_basis_subtotal"])
    sums["committed_mark_existing_basis"]=expected
    sums["decomposition_error_vs_existing_basis"]=sums["committed_mark_reconstructed"]-expected

    return {
        "day":day,
        "hour":int(obs.get("hour",0) or 0),
        "terminal_day":TERMINAL_DAY,
        "remaining_days_to_terminal":TERMINAL_DAY-day,
        "summary":sums,
        "assets":rows,
    }


def main():
    configure()
    snap_holder={}
    original_market=kg._process_market

    def capture_pre_market(state,env):
        obs0=plain(getv(state[0],"observation"))
        if isinstance(obs0,dict):
            day=int(obs0.get("day",0) or 0)
            hour=int(obs0.get("hour",0) or 0)
            if day==ANCHOR_DAY and hour==0 and "snap" not in snap_holder:
                sides=[]
                for p in (0,1):
                    op=plain(getv(state[p],"observation"))
                    sides.append(classify_side(op))
                snap_holder["snap"]={
                    "self":sides[SEAT],
                    "opponent":sides[1-SEAT],
                }
        return original_market(state,env)

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=body_only.agent
    kg._process_market=capture_pre_market
    try:
        env.run(players)
    finally:
        kg._process_market=original_market

    snap=snap_holder.get("snap")
    if snap is None:
        raise SystemExit("Day20 h0 pre-market snapshot not found")

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.strong-origin-v2.terminal-reachable-asset-surface.v0",
        "seed":SEED,
        "seat":SEAT,
        "anchor":{"day":ANCHOR_DAY,"hour":0,"phase":"pre_market","terminal_day":TERMINAL_DAY},
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        **snap,
        "environment_provenance":{
            "kaggle_environments_version":getattr(kaggle_environments,"__version__",None),
            "kaggriculture_module":str(getattr(kg,"__file__","")),
            "interpreter_sha256":hashlib.sha256(inspect.getsource(kg.interpreter).encode("utf-8")).hexdigest(),
        },
        "boundary":[
            "Snapshot phase is Day20 h0 immediately before public market processing, matching Dynamic Economic Surface v0.",\n            "READY means current output units already at the public harvest/output boundary at that snapshot.",
            "REACHABLE means committed units not READY at Day20 h0 whose public output boundary can be reached by the season terminal under the same explicit survival/WATER/FEED/timely-harvest assumptions used by the existing Committed Production valuation.",
            "NOT_REACHABLE means committed units on that same valuation basis whose public harvest/output boundary lies after terminal.",
            "The decomposition stops at Asset -> Output boundary. It does not assert completion of HARVEST -> carried -> shed -> SELL -> Cash.",
            "Displayed product price is used only to keep the same valuation basis as Committed Production; it is not realized Cash.",
            "No product preference, Action diagnosis, Candidate, or causal claim is introduced."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TERMINAL_REACHABLE_ASSET_SURFACE "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "self":snap["self"]["summary"],
        "opponent":snap["opponent"]["summary"],
        "terminal":payload["terminal"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
