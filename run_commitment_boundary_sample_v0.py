#!/usr/bin/env python3
"""Commitment Boundary Sample v0.

No candidate and no policy mutation.

Purpose:
Sample only the first few Day0-4 moments where purchased crop capital remains
uncommitted even though seed stock and empty land exist. Capture what the world
and both policies are actually doing at those moments.

This is not a full turn-by-turn observer. It intentionally exports only a few
representative boundary points.
"""
import copy
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"commitment_boundary_sample_v0_{SEED}.json")

action_trace={0:[],1:[]}


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


def summarize_obs(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    private=obs.get("private",{}) or {}
    tiles=farm.get("tiles",[]) or []
    empty=sum(1 for row in tiles for t in (row or []) if t is None)
    live=defaultdict(int)
    for row in tiles:
        for t in row or []:
            if isinstance(t,dict) and t.get("kind")=="PLANT" and t.get("crop"):
                live[str(t["crop"])]+=1
    return {
        "day":int(obs.get("day",0) or 0),
        "hour":int(obs.get("hour",0) or 0),
        "cash":float(farm.get("money",0) or 0),
        "workers":1+len(farm.get("hands",[]) or []),
        "empty_tiles":empty,
        "seed_stock":{k:int(v or 0) for k,v in (private.get("seeds",{}) or {}).items()},
        "live_crops":dict(sorted(live.items())),
    }


def wrap_agent(player,fn):
    def wrapped(obs):
        act=fn(obs)
        if int(obs.get("day",0) or 0)<4:
            action_trace[player].append({
                "state":summarize_obs(plain(obs)),
                "action":plain(act),
            })
        return act
    return wrapped


def market_with_time(state,env):
    before=len(exact.events)
    exact.measured_process_market(state,env)
    obs0=state[0].observation
    day=int(getv(obs0,"day",0) or 0)
    hour=int(getv(obs0,"hour",0) or 0)
    for e in exact.events[before:]:
        e["day"]=day
        e["hour"]=hour


def count_plant_orders(action,crop):
    n=0
    for key in ("farmer","hands"):
        xs=[action.get("farmer")] if key=="farmer" else list(action.get("hands",[]) or [])
        for a in xs:
            if isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="PLANT" and a[1]==crop:
                n+=1
    return n


def action_ops(action):
    out=[]
    f=action.get("farmer")
    if isinstance(f,(list,tuple)) and f: out.append(str(f[0]))
    for h in action.get("hands",[]) or []:
        if isinstance(h,(list,tuple)) and h: out.append(str(h[0]))
    return out


def buy_seed_by_turn(events,p):
    out=defaultdict(lambda:defaultdict(int))
    costs={"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
    for e in events:
        if int(e.get("player",-1))!=p or e.get("op")!="BUY_SEED": continue
        day=int(e.get("day",-1));hour=int(e.get("hour",-1))
        if not (0<=day<4): continue
        crop=str(e.get("item"))
        qty=int(e.get("qty",e.get("units",0)) or 0)
        if qty<=0 and crop in costs:
            qty=int(round(max(0.0,-float(e.get("cash_delta",0) or 0))/costs[crop]))
        out[(day,hour)][crop]+=qty
    return out


def build_boundaries(player,events):
    trace=action_trace[player]
    buys=buy_seed_by_turn(events,player)
    rows=[]
    for i,row in enumerate(trace):
        st=row["state"]; act=row["action"]
        key=(st["day"],st["hour"])
        next_stock=(trace[i+1]["state"]["seed_stock"] if i+1<len(trace)
                    else st["seed_stock"])
        crops=set(st["seed_stock"])|set(next_stock)|set(buys.get(key,{}))
        for crop in crops:
            before=int(st["seed_stock"].get(crop,0) or 0)
            bought=int(buys.get(key,{}).get(crop,0) or 0)
            after=int(next_stock.get(crop,0) or 0)
            planted=max(0,before+bought-after)
            queue_after=after
            # A real commitment stall must begin the turn with usable seed
            # already in stock. Same-turn BUY_SEED happens after unit actions
            # under public execution order and is therefore not plantable yet.
            if before<=0:
                continue
            if queue_after<=0 or st["empty_tiles"]<=0:
                continue
            if planted>0:
                continue
            rows.append({
                "crop":crop,
                "day":st["day"],
                "hour":st["hour"],
                "queue_before":before,
                "buy_units_this_turn":bought,
                "queue_after":queue_after,
                "empty_tiles":st["empty_tiles"],
                "workers":st["workers"],
                "cash":st["cash"],
                "live_crop_count":int(st["live_crops"].get(crop,0) or 0),
                "plant_orders_for_crop":count_plant_orders(act,crop),
                "unit_ops":action_ops(act),
                "action":act,
            })
    return rows


def select_samples(rows):
    # Keep this intentionally tiny: first stall overall + first MELON + first WHEAT.
    out=[]
    def add(x):
        if x and not any((y["day"],y["hour"],y["crop"])==(x["day"],x["hour"],x["crop"]) for y in out):
            out.append(x)
    add(rows[0] if rows else None)
    add(next((x for x in rows if x["crop"]=="MELON"),None))
    add(next((x for x in rows if x["crop"]=="WHEAT"),None))
    return out[:3]


def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()
    action_trace[0].clear();action_trace[1].clear()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    original=kg._process_market
    kg._process_market=market_with_time
    try:
        players=[None,None]
        for p in (0,1):
            fn=body_only.agent if p==SEAT else basecfg.OPPONENT
            players[p]=wrap_agent(p,fn)
        env.run(players)
    finally:
        kg._process_market=original

    self_rows=build_boundaries(SEAT,exact.events)
    opp_rows=build_boundaries(1-SEAT,exact.events)
    payload={
        "schema":"kaggriculture.strong-origin-v2.commitment-boundary-sample.v0",
        "seed":SEED,"seat":SEAT,
        "self":{
            "stall_count":len(self_rows),
            "samples":select_samples(self_rows),
        },
        "opponent":{
            "stall_count":len(opp_rows),
            "samples":select_samples(opp_rows),
        },
        "boundary":[
            "No action is changed; agents are wrapped only to record returned actions.",
            "A stall sample requires seed stock already present at turn start, at least one empty tile, no successful PLANT of that crop, and seed stock still remaining after the turn.",
            "Only first overall/MELON/WHEAT samples are retained; this is not exhaustive turn classification.",
            "Public execution order applies unit actions before market orders, so same-turn BUY_SEED is explicitly excluded as a commitment opportunity.",
            "PLANT success is derived from public seed-stock conservation plus executed BUY_SEED.",
            "Observed worker/action differences are descriptive and not yet causal."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMMITMENT_BOUNDARY_SAMPLE "+json.dumps({
        "seed":SEED,
        "self_stalls":len(self_rows),
        "opp_stalls":len(opp_rows),
        "self_samples":payload["self"]["samples"],
        "opp_samples":payload["opponent"]["samples"],
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
