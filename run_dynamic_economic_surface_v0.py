#!/usr/bin/env python3
"""Dynamic Economic Surface v0.

Observation-only replay of fixed five Battles over Day12 h0 -> Day20 h0.

Finite public basis:
- Asset State: present productive assets, held output, current harvestable units,
  and existing committed-production mark (kept as a separate valuation layer)
- Output State: carried / shed / on-hand product quantities
- Market State: shared inventory, displayed prices, exact realized SELL events
- Cash State: cash before/after public market processing
- Time State: day/hour and remaining season turns

No mode labels, strategy classes, Action diagnosis, Candidate, or causal story.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_asset_formation_map_v0 as af
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"dynamic_economic_surface_v0_{SEED}_seat{SEAT}.json")
START_T=12*24
END_T=20*24

surface_turns=[]

def plain(v):
    return af.plain(v)

def getv(x,key,default=None):
    return af.getv(x,key,default)

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

def qty_map(src):
    src=src if isinstance(src,dict) else {}
    return {item:int(src.get(item,0) or 0) for item in econ.PRODUCTS}

def stock_snapshot(obs):
    private=obs.get("private",{}) or {}
    shed=qty_map(private.get("shed",{}) or {})
    carried={item:0 for item in econ.PRODUCTS}
    for inv in private.get("inventories",[]) or []:
        if not isinstance(inv,dict):
            continue
        for item in econ.PRODUCTS:
            carried[item]+=int(inv.get(item,0) or 0)
    return {
        "shed_by_item":shed,
        "carried_by_item":carried,
        "on_hand_by_item":{item:shed[item]+carried[item] for item in econ.PRODUCTS},
    }

def asset_snapshot(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    day=int(obs.get("day",0) or 0)
    instances=[]
    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,tile in enumerate(row or []):
            z=af.asset_instance(tile,x,y,day)
            if z is not None:
                instances.append(z)
    s=af.summarize(instances)
    return {
        typ:{
            "present_asset_count":int(v["present_asset_count"]),
            "held_output_units":int(v["held_output_units"]),
            "current_harvestable_units":int(v["current_harvestable_units"]),
            "near_window_base_units_conditional":int(v["near_window_base_units_conditional"]),
            "next_boundary_days":list(v["next_boundary_days"]),
        }
        for typ,v in s.items()
    }

def side_snapshot(obs):
    d=econ.derive_side(obs)
    return {
        "cash":float(d["cash"]),
        "time":{
            "day":int(d["day"]),
            "hour":int(d["hour"]),
            "remaining_season_turns":int(d["uncommitted_capacity"]["remaining_season_turns"]),
        },
        "asset_by_type":asset_snapshot(obs),
        "committed_production_mark":{
            "crop":float(d["committed_production"]["crop_current_price_potential_mark"]),
            "animal":float(d["committed_production"]["animal_base_current_price_potential_mark"]),
            "subtotal":float(d["committed_production"]["same_basis_subtotal"]),
            "crop_mark_by_type":{
                k:float(v) for k,v in d["committed_production"]["crop_mark_by_type"].items()
            },
            "animal_mark_by_type":{
                k:float(v) for k,v in d["committed_production"]["animal_mark_by_type"].items()
            },
        },
        "stock":stock_snapshot(obs),
        "inventory_display_mark":{
            "total":float(d["liquidatable_inventory"]["display_price_mark"]),
            "by_item":{
                item:{
                    "quantity":int(v["quantity"]),
                    "price":float(v["price"]),
                    "mark":float(v["mark"]),
                }
                for item,v in d["liquidatable_inventory"]["by_item"].items()
            },
        },
    }

def common_market(obs):
    market=obs.get("market",{}) or {}
    inv=market.get("inventory",{}) or {}
    prices=market.get("prices",{}) or {}
    return {
        "inventory_by_item":{item:int(inv.get(item,0) or 0) for item in econ.PRODUCTS},
        "displayed_price_by_item":{item:float(prices.get(item,0) or 0) for item in econ.PRODUCTS},
    }

def aggregate_events(events):
    out={str(p):{
        "sell_units_by_item":{item:0 for item in econ.PRODUCTS},
        "sell_cash_by_item":{item:0.0 for item in econ.PRODUCTS},
        "market_cash_delta_all_ops":0.0,
    } for p in (0,1)}
    for e in events:
        p=str(int(e["player"]))
        out[p]["market_cash_delta_all_ops"]+=float(e.get("cash_delta",0) or 0)
        if e.get("op")=="SELL" and e.get("item") in econ.PRODUCTS:
            item=e["item"]
            out[p]["sell_units_by_item"][item]+=1
            out[p]["sell_cash_by_item"][item]+=float(e.get("cash_delta",0) or 0)
    return out

def measured_market(state,env):
    obs0=plain(getv(state[0],"observation"))
    if not isinstance(obs0,dict):
        return exact.measured_process_market(state,env)
    day=int(obs0.get("day",0) or 0)
    hour=int(obs0.get("hour",0) or 0)
    t=day*24+hour
    in_surface=START_T<=t<=END_T

    if in_surface:
        before=[]
        for p in (0,1):
            before.append(side_snapshot(plain(getv(state[p],"observation"))))
        market_before=common_market(obs0)
    else:
        before=None
        market_before=None

    n0=len(exact.events)
    exact.measured_process_market(state,env)
    new_events=[plain(e) for e in exact.events[n0:]]
    for e in new_events:
        e["day"]=day
        e["hour"]=hour

    if in_surface:
        after=[]
        for p in (0,1):
            after.append(side_snapshot(plain(getv(state[p],"observation"))))
        surface_turns.append({
            "day":day,
            "hour":hour,
            "turn_index":t,
            "before":{"0":before[0],"1":before[1]},
            "after_market":{"0":after[0],"1":after[1]},
            "market_before":market_before,
            "realized_market_events":new_events,
            "realized_by_player":aggregate_events(new_events),
        })

def main():
    configure()
    surface_turns.clear()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    original=kg._process_market
    kg._process_market=measured_market
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=body_only.agent
        env.run(players)
    finally:
        kg._process_market=original

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.strong-origin-v2.dynamic-economic-surface.v0",
        "seed":SEED,
        "seat":SEAT,
        "window":{"start_day":12,"end_day":20,"endpoint_included":True},
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "surface_turns":surface_turns,
        "boundary":[
            "The finite observation basis is Asset / Output / Market / Cash / Time only.",
            "Asset quantities remain separated by asset type; product stock and realized SELL remain separated by item.",
            "Committed-production mark is retained only as the existing public valuation layer and is not added to Cash or inventory.",
            "Market snapshots are shared public market inventory/displayed prices immediately before public market processing.",
            "Cash and stock before/after snapshots bracket only public market processing at the same turn.",
            "The Day20 h0 point is retained as an endpoint; interval event aggregation may exclude it when computing Day19->20.",
            "No exploration/expansion/overheat/withdrawal mode is assigned.",
            "No Action diagnosis, strategy interpretation, Candidate, or causal conversion is inferred."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DYNAMIC_ECONOMIC_SURFACE "+json.dumps({
        "seed":SEED,
        "seat":SEAT,
        "surface_turn_count":len(surface_turns),
        "terminal":payload["terminal"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
