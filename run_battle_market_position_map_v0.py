#!/usr/bin/env python3
"""Battle Market Position Map v0.

Projects fixed Battles onto Market State Schedule v0.

Public-world observations only:
- shared market inventory and displayed quote price
- SELL-able shed inventory for each player
- carried inventory kept separate (not SELL-able)
- exact realized SELL units / price / Cash
- Cash state

No profitability score, causality, or policy diagnosis.
"""
import json,os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"battle_market_position_map_v0_{SEED}_seat{SEAT}.json")
PRODUCTS=("WHEAT","MELON","STRAWBERRY","MILK","WOOL")
_current_day=0
_current_hour=0

def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)

def getv(x,key,default=None):
    if isinstance(x,dict):return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

def measured_market_with_time(state,env):
    global _current_day,_current_hour
    obs0=state[0].observation
    _current_day=int(getv(obs0,"day",0) or 0)
    _current_hour=int(getv(obs0,"hour",0) or 0)
    before=len(exact.events)
    exact.measured_process_market(state,env)
    for e in exact.events[before:]:
        e["day"]=_current_day
        e["hour"]=_current_hour

def side_position(obs):
    p=int(obs["player"])
    farm=(obs.get("farms") or [{},{}])[p]
    private=obs.get("private",{}) or {}
    shed=private.get("shed",{}) or {}
    carried={x:0 for x in PRODUCTS}
    for inv in private.get("inventories",[]) or []:
        if not isinstance(inv,dict):continue
        for item in PRODUCTS:
            carried[item]+=int(inv.get(item,0) or 0)
    return {
      "cash":float(farm.get("money",0) or 0),
      "sellable_shed":{item:int(shed.get(item,0) or 0) for item in PRODUCTS},
      "carried_not_sellable":carried
    }

def main():
    configure()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    initial=[float(env.state[p].observation.farms[p].money) for p in (0,1)]
    original_market=kg._process_market
    kg._process_market=measured_market_with_time
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=body_only.agent
        env.run(players)
    finally:
        kg._process_market=original_market

    timeline=[]
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2:continue
        so=plain(getv(step[SEAT],"observation"))
        oo=plain(getv(step[1-SEAT],"observation"))
        if not isinstance(so,dict) or not isinstance(oo,dict):continue
        d=int(so.get("day",0) or 0);h=int(so.get("hour",0) or 0)
        if not (12<=d<=18):continue
        market=so.get("market",{}) or {}
        town=so.get("town",{}) or {}
        timeline.append({
          "step":step_index,"day":d,"hour":h,
          "market":{
            "inventory":{item:int((market.get("inventory",{}) or {}).get(item,0) or 0) for item in PRODUCTS},
            "price":{item:float((market.get("prices",{}) or {}).get(item,0) or 0) for item in PRODUCTS},
            "unlocked_shops":list(town.get("unlocked_shops",[]) or [])
          },
          "self":side_position(so),
          "opponent":side_position(oo)
        })

    sell_events=[
      plain(e) for e in exact.events
      if e.get("op")=="SELL"
      and e.get("item") in PRODUCTS
      and 12<=int(e.get("day",-1))<=18
    ]

    terminal=[float(x.reward) for x in env.state]
    validation=[]
    for p in (0,1):
        net=sum(float(v) for v in exact.ledger[p].values())
        validation.append({
          "player":p,
          "initial_cash":initial[p],
          "market_cash_flow_net":net,
          "reconstructed_terminal":initial[p]+net,
          "actual_terminal":terminal[p],
          "error":initial[p]+net-terminal[p]
        })

    payload={
      "schema":"kaggriculture.battle-market-position-map.v0",
      "market_schedule_id":"MSS-0001",
      "public_rule_commit":"b2405492c8403f6649f9317290f215e0290a2425",
      "seed":SEED,"seat":SEAT,
      "products":list(PRODUCTS),
      "terminal":{"self":terminal[SEAT],"opponent":terminal[1-SEAT],"margin":terminal[SEAT]-terminal[1-SEAT]},
      "timeline":timeline,
      "sell_events":sell_events,
      "cash_validation":validation,
      "boundary":[
        "SELL-able inventory means shed inventory only. Carried inventory is kept separate.",
        "Displayed market price is shared public State. Realized SELL price is taken from exact successful unit execution.",
        "Timeline State is post-interpreter recorded State; market/town transitions within the preceding turn have already occurred.",
        "No claim links a specific produced unit to a specific sold unit or later Cash use.",
        "No profitability score, expected score, cause, Candidate, or policy conclusion."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BATTLE_MARKET_POSITION_MAP "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "timeline_points":len(timeline),"sell_events":len(sell_events),
      "cash_errors":[x["error"] for x in validation],
      "terminal":payload["terminal"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
