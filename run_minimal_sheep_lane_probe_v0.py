#!/usr/bin/env python3
"""Minimal SHEEP Lane Probe v0 paired runner.

Compares Body-only v0 vs Body-only + one minimal early SHEEP lane.
Primary read is the predicted Accounting Bridge:
Day4 animal composition -> Day4-8 non-WHEAT realization -> operating-adjusted
surplus -> productive spend -> Day8 State -> terminal.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as baseline
import strong_origin_v2_minimal_sheep_lane_v0 as candidate

SEED=int(os.environ.get("BATTLE_SEED","7351"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"minimal_sheep_lane_probe_v0_{SEED}.json")
PRODUCTIVE_OPS=("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL")


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


def first_obs_for_day(env,seat,day):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        obs=plain(getv(step[seat],"observation"))
        if isinstance(obs,dict) and int(obs.get("day",0) or 0)==day:
            return obs
    return None


def state_summary(obs):
    if not obs:return None
    side=econ.derive_side(obs)
    p=int(obs["player"])
    farm=obs["farms"][p]
    crops=side["committed_production"]["crop_count"]
    animals=side["committed_production"]["animal_count"]
    return {
        "cash":float(side["cash"]),
        "land_quadrants":len(farm.get("unlocked_quadrants",[]) or []),
        "unlocked_tiles":int(side["uncommitted_capacity"]["unlocked_tiles"]),
        "empty_unlocked_tiles":int(side["uncommitted_capacity"]["empty_unlocked_tiles"]),
        "productive_assets":int(sum(crops.values())+sum(animals.values())),
        "production_potential_mark":float(side["committed_production"]["same_basis_subtotal"]),
        "crop_count":dict(crops),
        "animal_count":dict(animals),
        "shed_animals":{
            a:int((obs.get("private",{}).get("shed",{}) or {}).get(a,0) or 0)
            for a in ("COW","SHEEP","GOOSE")
        },
        "carried_animals":{
            a:sum(int((inv or {}).get(a,0) or 0) for inv in (obs.get("private",{}).get("inventories",[]) or []))
            for a in ("COW","SHEEP","GOOSE")
        },
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

    def market_with_time(state,env):
        before=len(exact.events)
        obs0=state[0].observation
        day=int(getv(obs0,"day",0) or 0)
        hour=int(getv(obs0,"hour",0) or 0)
        exact.measured_process_market(state,env)
        for e in exact.events[before:]:
            e["day"]=day;e["hour"]=hour

    original=kg._process_market
    kg._process_market=market_with_time
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        initial=[float(env.state[p].observation.farms[p].money) for p in (0,1)]
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=agent.agent
        env.run(players)
    finally:
        kg._process_market=original

    terminal=[float(x.reward) for x in env.state]
    net=sum(float(v) for v in exact.ledger[SEAT].values())
    err=initial[SEAT]+net-terminal[SEAT]

    early_days={str(d):state_summary(first_obs_for_day(env,SEAT,d)) for d in (0,1,2,3,4)}
    day4=early_days["4"]
    day8=state_summary(first_obs_for_day(env,SEAT,8))

    ev=[e for e in exact.events if int(e.get("player",-1))==SEAT and 4<=int(e.get("day",-1))<8]
    sell=defaultdict(float)
    productive=defaultdict(float)
    operating=defaultdict(float)
    for e in ev:
        op=e.get("op")
        item=e.get("item")
        delta=float(e.get("cash_delta",0) or 0)
        if op=="SELL":
            sell[str(item)]+=delta
        elif op in PRODUCTIVE_OPS:
            productive[str(op)]+=max(0.0,-delta)
        elif op=="BUY_PRODUCT":
            operating[str(item)]+=max(0.0,-delta)

    realized_sell=sum(sell.values())
    operating_spend=sum(operating.values())
    surplus=realized_sell-operating_spend
    productive_spend=sum(productive.values())
    cash_growth=day8["cash"]-day4["cash"]

    sheep_buy_events=[
        {"day":int(e.get("day",-1)),"hour":int(e.get("hour",-1)),"cash_delta":float(e.get("cash_delta",0) or 0)}
        for e in exact.events
        if int(e.get("player",-1))==SEAT and e.get("op")=="BUY_ANIMAL" and e.get("item")=="SHEEP"
    ]
    sheep_buys=len(sheep_buy_events)

    sheep_tile_history=[]
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        obs=plain(getv(step[SEAT],"observation"))
        if not isinstance(obs,dict): continue
        farm=obs.get("farms",[{}])[SEAT]
        n=0
        for row in farm.get("tiles",[]) or []:
            for t in row or []:
                if isinstance(t,dict) and t.get("animal")=="SHEEP":
                    n+=1
        if n:
            sheep_tile_history.append({
                "step":step_index,
                "day":int(obs.get("day",0) or 0),
                "hour":int(obs.get("hour",0) or 0),
                "count":n,
            })
    cow_buys=sum(
        1 for e in exact.events
        if int(e.get("player",-1))==SEAT and e.get("op")=="BUY_ANIMAL" and e.get("item")=="COW"
    )

    return {
        "terminal":{
            "self":terminal[SEAT],
            "opponent":terminal[1-SEAT],
            "margin":terminal[SEAT]-terminal[1-SEAT],
            "win":terminal[SEAT]>terminal[1-SEAT],
        },
        "cash_reconstruction_error":err,
        "direct_reachability":{
            "executed_sheep_buys":sheep_buys,
            "sheep_buy_events":sheep_buy_events,
            "sheep_first_tile_state":sheep_tile_history[0] if sheep_tile_history else None,
            "sheep_last_tile_state":sheep_tile_history[-1] if sheep_tile_history else None,
            "sheep_tile_observed_steps":len(sheep_tile_history),
            "executed_cow_buys":cow_buys,
            "day4_cows":day4["animal_count"].get("COW",0),
            "day4_sheep":day4["animal_count"].get("SHEEP",0),
        },
        "early_days":early_days,
        "day4":day4,
        "day4_to_day8":{
            "sell_by_item":dict(sorted(sell.items())),
            "realized_sell":realized_sell,
            "non_wheat_sell":sum(v for k,v in sell.items() if k!="WHEAT"),
            "operating_by_item":dict(sorted(operating.items())),
            "operating_spend":operating_spend,
            "surplus_after_operating":surplus,
            "productive_spend_by_op":dict(sorted(productive.items())),
            "productive_spend":productive_spend,
            "cash_growth":cash_growth,
            "bridge_error":surplus-productive_spend-cash_growth,
        },
        "day8":day8,
        "telemetry":plain(agent.get_telemetry()),
    }


b=run(baseline)
c=run(candidate)
payload={
    "schema":"kaggriculture.strong-origin-v2.minimal-sheep-lane-probe.paired.v0",
    "seed":SEED,"seat":SEAT,
    "baseline":b,"candidate":c,
    "delta":{
        "terminal_self":c["terminal"]["self"]-b["terminal"]["self"],
        "terminal_margin":c["terminal"]["margin"]-b["terminal"]["margin"],
        "day4_to_day8_non_wheat_sell":c["day4_to_day8"]["non_wheat_sell"]-b["day4_to_day8"]["non_wheat_sell"],
        "day4_to_day8_surplus":c["day4_to_day8"]["surplus_after_operating"]-b["day4_to_day8"]["surplus_after_operating"],
        "day4_to_day8_productive_spend":c["day4_to_day8"]["productive_spend"]-b["day4_to_day8"]["productive_spend"],
        "day8_productive_assets":c["day8"]["productive_assets"]-b["day8"]["productive_assets"],
        "day8_production_potential":c["day8"]["production_potential_mark"]-b["day8"]["production_potential_mark"],
        "day8_land_quadrants":c["day8"]["land_quadrants"]-b["day8"]["land_quadrants"],
    },
    "boundary":[
        "Baseline is Strong Origin v2 Body-only v0.",
        "Candidate adds only the minimal early SHEEP lane while preserving the existing COW target.",
        "Direct reachability requires Day4 COW count not to fall below baseline and Day4 SHEEP count to increase.",
        "The predicted bridge is non-WHEAT realization -> operating-adjusted surplus -> productive spend -> Day8 State.",
        "Cash is fungible; no sale dollar is assigned to a later purchase.",
        "Preflight/fresh comparison does not adopt the candidate automatically."
    ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("MINIMAL_SHEEP_LANE_PROBE "+json.dumps({
    "seed":SEED,"seat":SEAT,
    "baseline_terminal":b["terminal"],
    "candidate_terminal":c["terminal"],
    "candidate_reachability":c["direct_reachability"],
    "delta":payload["delta"],
    "candidate_bridge":c["day4_to_day8"],
},ensure_ascii=False,separators=(",",":")))
