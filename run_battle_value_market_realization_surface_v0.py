#!/usr/bin/env python3
"""Battle Value Market Realization Surface v0.

Observation-only replay for Day20->24 on the fixed five-Battle map.

Records only public-world Market/Cash facts:
- SELL-able harvested inventory immediately before each market process
- exact realized SELL units and Cash by item
- displayed market price at each SELL
- Cash immediately before market processing

No BUY diagnosis, Action reasoning, causal conversion claim, Representation,
Evaluation, Direction, or Candidate.
"""
import json, os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"battle_value_market_realization_surface_v0_{SEED}_seat{SEAT}.json")

market_turns=[]
sell_events=[]

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)

def getv(x,key,default=None):
    if isinstance(x,dict): return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

def side_snapshot(obs):
    s=econ.derive_side(obs)
    return {
        "cash":float(s["cash"]),
        "inventory_mark":float(s["liquidatable_inventory"]["display_price_mark"]),
        "inventory_by_item":s["liquidatable_inventory"]["by_item"],
    }

def measured_market_with_surface(state,env):
    obs0=plain(getv(state[0],"observation"))
    if not isinstance(obs0,dict):
        return exact.measured_process_market(state,env)
    d=int(obs0.get("day",0) or 0)
    h=int(obs0.get("hour",0) or 0)
    t=d*24+h

    in_surface=(20*24 <= t <= 24*24)
    if in_surface:
        before_sides=[]
        for p in (0,1):
            op=plain(getv(state[p],"observation"))
            before_sides.append(side_snapshot(op))
        turn={
            "day":d,"hour":h,
            "before":[before_sides[0],before_sides[1]],
        }
    else:
        turn=None

    before_n=len(exact.events)
    exact.measured_process_market(state,env)

    for e in exact.events[before_n:]:
        e["day"]=d;e["hour"]=h
        if e.get("op")=="SELL" and 20*24 <= t < 24*24:
            sell_events.append(plain(e))

    if turn is not None:
        market_turns.append(turn)

def main():
    configure()
    market_turns.clear();sell_events.clear()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    original_market=kg._process_market
    kg._process_market=measured_market_with_surface
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=body_only.agent
        env.run(players)
    finally:
        kg._process_market=original_market

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.strong-origin-v2.battle-value-market-realization-surface.v0",
        "seed":SEED,
        "seat":SEAT,
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "surface":{"start_day":20,"end_day":24,"end_exclusive_for_sell":True},
        "market_turns":market_turns,
        "sell_events":sell_events,
        "boundary":[
            "Inventory snapshots are harvested SELL-able inventory immediately before public market processing at each observed turn.",
            "SELL events are exact realized market Cash events from the validated public market processor; one event is one sold unit under the current logger.",
            "The Day24 h0 snapshot is retained as an endpoint but SELL aggregation is Day20 h0 inclusive to Day24 h0 exclusive.",
            "Starting inventory is not assumed to be the source of later SELL units because inventory can be replenished during the interval.",
            "No claim is made that declining committed-production value is the same value later realized as SELL/Cash.",
            "No BUY, Action, policy, Representation, Evaluation, Direction, Candidate, or causal diagnosis is introduced."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BATTLE_VALUE_MARKET_REALIZATION_SURFACE "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "market_turns":len(market_turns),
        "sell_events":len(sell_events),
        "terminal":payload["terminal"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
