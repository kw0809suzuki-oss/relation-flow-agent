#!/usr/bin/env python3
"""Paired COW Pickup Reservation Probe v0.

A/B:
- baseline: Strong Origin v2 Body-only v0
- candidate: same body with non-preemptive livestock arbitration only

No PLANT action is forced.
"""
import json,os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as baseline
import strong_origin_v2_cow_pickup_reservation_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"cow_pickup_reservation_probe_v0_{SEED}.json")
SEED_COST={"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
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
    if isinstance(x,dict):return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def first_obs(env,seat,day):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        obs=plain(getv(step[seat],"observation"))
        if isinstance(obs,dict) and int(obs.get("day",0) or 0)==day:
            return obs
    return None


def state_summary(obs):
    side=econ.derive_side(obs)
    p=int(obs["player"])
    farm=obs["farms"][p]
    crops=side["committed_production"]["crop_count"]
    animals=side["committed_production"]["animal_count"]
    seeds=(obs.get("private",{}) or {}).get("seeds",{}) or {}
    return {
      "cash":float(side["cash"]),
      "land_quadrants":len(farm.get("unlocked_quadrants",[]) or []),
      "empty_tiles":int(side["uncommitted_capacity"]["empty_unlocked_tiles"]),
      "productive_assets":int(sum(crops.values())+sum(animals.values())),
      "production_potential_mark":float(side["committed_production"]["same_basis_subtotal"]),
      "crop_count":dict(crops),
      "animal_count":dict(animals),
      "seed_stock":{k:int(v or 0) for k,v in seeds.items()},
    }


def configure(agent):
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    agent.reset_telemetry()


def run(agent):
    configure(agent)
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    def measured(state,env):
        before=len(exact.events)
        exact.measured_process_market(state,env)
        obs0=state[0].observation
        day=int(getv(obs0,"day",0) or 0);hour=int(getv(obs0,"hour",0) or 0)
        for e in exact.events[before:]:
            e["day"]=day;e["hour"]=hour

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    obs_initial=plain(env.state[SEAT].observation)
    opening_seeds=(obs_initial.get("private",{}) or {}).get("seeds",{}) or {}

    original=kg._process_market
    kg._process_market=measured
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=agent.agent
        env.run(players)
    finally:
        kg._process_market=original

    terminal=[float(x.reward) for x in env.state]
    d4=state_summary(first_obs(env,SEAT,4))
    d8=state_summary(first_obs(env,SEAT,8))

    buy_units=defaultdict(int);buy_cash=defaultdict(float)
    for e in exact.events:
        if int(e.get("player",-1))!=SEAT or e.get("op")!="BUY_SEED":continue
        if not (0<=int(e.get("day",-1))<4):continue
        crop=str(e.get("item"))
        if crop not in SEED_COST:continue
        cash=max(0.0,-float(e.get("cash_delta",0) or 0))
        qty=int(e.get("qty",e.get("units",0)) or 0)
        if qty<=0:qty=int(round(cash/SEED_COST[crop]))
        buy_units[crop]+=qty;buy_cash[crop]+=cash

    crops=set(SEED_COST)|set(opening_seeds)|set(buy_units)|set(d4["seed_stock"])
    available=sum(int(opening_seeds.get(c,0) or 0)+int(buy_units.get(c,0) or 0) for c in crops)
    idle=sum(int(d4["seed_stock"].get(c,0) or 0) for c in crops)
    committed=available-idle
    idle_capital=sum(int(d4["seed_stock"].get(c,0) or 0)*SEED_COST.get(c,0) for c in crops)

    return {
      "terminal":{"self":terminal[SEAT],"opponent":terminal[1-SEAT],"margin":terminal[SEAT]-terminal[1-SEAT],"win":terminal[SEAT]>terminal[1-SEAT]},
      "day4":d4,
      "commitment":{
        "available_seed_units":available,
        "committed_seed_units":committed,
        "day4_idle_seed_units":idle,
        "commitment_rate":committed/available if available else None,
        "day4_idle_capital":idle_capital,
        "buy_seed_units":dict(sorted(buy_units.items())),
        "buy_seed_cash":dict(sorted(buy_cash.items())),
      },
      "day8":d8,
      "telemetry":plain(agent.get_telemetry()),
    }


b=run(baseline)
c=run(candidate)
payload={
 "schema":"kaggriculture.strong-origin-v2.nonpreemptive-livestock-probe.paired.v0",
 "seed":SEED,"seat":SEAT,
 "baseline":b,"candidate":c,
 "delta":{
   "terminal_self":c["terminal"]["self"]-b["terminal"]["self"],
   "terminal_margin":c["terminal"]["margin"]-b["terminal"]["margin"],
   "commitment_rate":c["commitment"]["commitment_rate"]-b["commitment"]["commitment_rate"],
   "day4_idle_capital":c["commitment"]["day4_idle_capital"]-b["commitment"]["day4_idle_capital"],
   "day4_assets":c["day4"]["productive_assets"]-b["day4"]["productive_assets"],
   "day4_potential":c["day4"]["production_potential_mark"]-b["day4"]["production_potential_mark"],
   "day8_assets":c["day8"]["productive_assets"]-b["day8"]["productive_assets"],
   "day8_potential":c["day8"]["production_potential_mark"]-b["day8"]["production_potential_mark"],
 },
 "boundary":[
   "Candidate changes only duplicate shed COW PICKUP arbitration.",
   "No PLANT or crop action is forced.",
   "Within one decision pass, shed COW PICKUP requests cannot exceed the currently observed shed COW quantity.",
   "All market livestock rules, crop targets, COW targets, HIRE, LAND, livestock maintenance and D14 closure are unchanged.",
   "No adoption is automatic."
 ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("COW_PICKUP_RESERVATION_PAIR "+json.dumps({"seed":SEED,"delta":payload["delta"],"baseline_terminal":b["terminal"],"candidate_terminal":c["terminal"],"baseline_commitment":b["commitment"],"candidate_commitment":c["commitment"]},ensure_ascii=False,separators=(",",":")))
