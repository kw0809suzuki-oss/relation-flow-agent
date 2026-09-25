#!/usr/bin/env python3
"""Production Downstream Boundary Surface v0.

Tracks only productive assets that exist at the Day20 h0 pre-market anchor.

On the exact same Day20 displayed-price / Committed Production basis, project:
  anchor committed potential
    -> same-basis units that actually reach the public Output boundary by terminal
    -> same-basis units harvested from those anchor assets

Extra post-anchor bonus production beyond the Day20 committed basis is recorded
separately and never used to inflate passage of the anchor residual.

Stops at HARVEST -> carried. No shed/SELL/Cash lineage is asserted here.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_terminal_reachable_asset_surface_v0 as reach
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"production_downstream_boundary_surface_v0_{SEED}_seat{SEAT}.json")
ANCHOR_DAY=20
TERMINAL_DAY=econ.SEASON_DAYS

_original_apply=kg._apply_unit_action
_original_refresh_plants=kg._daily_refresh_plants
_original_refresh_animals=kg._daily_refresh_animals

farm_to_player={}
anchor=None
ledgers={0:{},1:{}}
current_player=None
current_day=None
current_hour=None
main_calls=0
day_start_seen=set()


def plain(v):
    return reach.plain(v)


def getv(x,key,default=None):
    return reach.getv(x,key,default)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()


def asset_signature(tile):
    if not isinstance(tile,dict):
        return None
    if tile.get("kind")=="PLANT" and tile.get("crop") in econ.CROPS:
        return ("crop",tile["crop"],int(tile.get("planted_day",-999)))
    if tile.get("animal") in econ.ANIMALS:
        return ("animal",tile["animal"],int(tile.get("placed_day",-999)))
    return None


def get_tile(farm,x,y):
    try:
        return farm["tiles"][y][x]
    except Exception:
        return None


def matches(farm,row):
    return asset_signature(get_tile(farm,row["x"],row["y"]))==tuple(row["signature"])


def tile_yield(farm,row):
    if not matches(farm,row):
        return 0
    tile=get_tile(farm,row["x"],row["y"])
    return max(0,int(tile.get("yield_units",0) or 0))


def init_anchor_side(obs):
    side=reach.classify_side(obs)
    rows={}
    for z in side["assets"]:
        sig=(
            z["asset_class"],
            z["asset_type"],
            int(z["origin_day"]),
        )
        key=f'{z["x"]},{z["y"]}'
        rule=econ.CROPS[z["asset_type"]] if z["asset_class"]=="crop" else econ.ANIMALS[z["asset_type"]]
        rows[key]={
            "x":int(z["x"]),
            "y":int(z["y"]),
            "signature":list(sig),
            "asset_class":z["asset_class"],
            "asset_type":z["asset_type"],
            "product":z["product"],
            "origin_day":int(z["origin_day"]),
            "price":float(z["price"]),
            "ongoing":bool(rule.get("ongoing",True)) if z["asset_class"]=="crop" else True,
            "first_output_boundary_day":int(z["first_output_boundary_day"]),
            "potential_units_same_basis":int(z["potential_units_same_basis"]),
            "initial_ready_units":int(z["ready_units"]),
            "output_reached_same_basis_units":int(z["ready_units"]),
            "harvested_same_basis_units":0,
            "actual_harvested_units":0,
            "extra_output_units_beyond_anchor_basis":0,
            "maturity_boundary_counted":bool(z["ready_units"]>0),
            "active":True,
            "inactive_reason":None,
        }
    return side,rows


def maybe_deactivate(farm,p,reason):
    for row in ledgers[p].values():
        if row["active"] and not matches(farm,row):
            row["active"]=False
            row["inactive_reason"]=reason


def count_nonongoing_maturity(farm,p,day):
    key=(p,int(day))
    if key in day_start_seen:
        return
    day_start_seen.add(key)
    for row in ledgers[p].values():
        if not row["active"] or row["asset_class"]!="crop" or row["ongoing"]:
            continue
        if row["maturity_boundary_counted"]:
            continue
        if int(row["first_output_boundary_day"])!=int(day):
            continue
        if not matches(farm,row):
            row["active"]=False
            row["inactive_reason"]="missing_at_maturity_boundary"
            continue
        actual=tile_yield(farm,row)
        remaining=max(0,row["potential_units_same_basis"]-row["output_reached_same_basis_units"])
        credited=min(actual,remaining)
        extra=max(0,actual-credited)
        row["output_reached_same_basis_units"]+=credited
        row["extra_output_units_beyond_anchor_basis"]+=extra
        row["maturity_boundary_counted"]=True


def wrapped_refresh_plants(farm,current_day,turns_per_day):
    p=farm_to_player.get(id(farm))
    before={}
    if p is not None and current_day>=ANCHOR_DAY:
        for key,row in ledgers[p].items():
            if row["active"] and row["asset_class"]=="crop" and row["ongoing"]:
                before[key]=tile_yield(farm,row)
    _original_refresh_plants(farm,current_day,turns_per_day)
    if p is not None and current_day>=ANCHOR_DAY:
        for key,b in before.items():
            row=ledgers[p][key]
            if not row["active"]:
                continue
            if not matches(farm,row):
                row["active"]=False
                row["inactive_reason"]="plant_refresh_removed_asset"
                continue
            a=tile_yield(farm,row)
            actual_added=max(0,a-b)
            if actual_added<=0:
                continue
            remaining=max(0,row["potential_units_same_basis"]-row["output_reached_same_basis_units"])
            # Existing committed basis counts one base unit per scheduled ongoing-crop event.
            credited=min(1,remaining)
            row["output_reached_same_basis_units"]+=credited
            row["extra_output_units_beyond_anchor_basis"]+=max(0,actual_added-credited)


def wrapped_refresh_animals(farm,day):
    p=farm_to_player.get(id(farm))
    before={}
    if p is not None and day>=ANCHOR_DAY:
        for key,row in ledgers[p].items():
            if row["active"] and row["asset_class"]=="animal":
                before[key]=tile_yield(farm,row)
    _original_refresh_animals(farm,day)
    if p is not None and day>=ANCHOR_DAY:
        for key,b in before.items():
            row=ledgers[p][key]
            if not row["active"]:
                continue
            if not matches(farm,row):
                row["active"]=False
                row["inactive_reason"]="animal_refresh_removed_asset"
                continue
            a=tile_yield(farm,row)
            actual_added=max(0,a-b)
            if actual_added<=0:
                continue
            remaining=max(0,row["potential_units_same_basis"]-row["output_reached_same_basis_units"])
            # Existing committed animal basis is base production; care bonus is extra.
            credited=min(1,remaining)
            row["output_reached_same_basis_units"]+=credited
            row["extra_output_units_beyond_anchor_basis"]+=max(0,actual_added-credited)


def inv_qty(private,idx,product):
    invs=private.get("inventories",[]) or []
    if idx>=len(invs) or not isinstance(invs[idx],dict):
        return 0
    return int(invs[idx].get(product,0) or 0)


def wrapped_apply(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
    global main_calls,current_player,current_day,current_hour
    if idx==0:
        p=main_calls%2
        hour=(main_calls//2)%int(turns_per_day)
        main_calls+=1
        current_player=p
        current_day=int(day)
        current_hour=int(hour)
        farm_to_player[id(farm)]=p
        if anchor is not None and day>=ANCHOR_DAY and hour==0:
            count_nonongoing_maturity(farm,p,day)

    p=farm_to_player.get(id(farm),current_player)
    op=action[0] if isinstance(action,list) and action else None
    pos=kg._farmer_position(farm,idx)
    row=None
    before_inv=None
    if (
        anchor is not None and p in ledgers and
        day>=ANCHOR_DAY and op=="HARVEST" and pos is not None
    ):
        key=f"{int(pos[0])},{int(pos[1])}"
        cand=ledgers[p].get(key)
        if cand is not None and cand["active"] and matches(farm,cand):
            row=cand
            before_inv=inv_qty(private,idx,row["product"])

    _original_apply(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)

    if row is not None:
        after_inv=inv_qty(private,idx,row["product"])
        actual=max(0,after_inv-before_inv)
        available=max(0,row["output_reached_same_basis_units"]-row["harvested_same_basis_units"])
        credited=min(actual,available)
        row["actual_harvested_units"]+=actual
        row["harvested_same_basis_units"]+=credited

    if anchor is not None and p in ledgers and day>=ANCHOR_DAY:
        maybe_deactivate(farm,p,"unit_action_replaced_or_removed_asset")


def measured_market(state,env):
    global anchor
    obs0=plain(getv(state[0],"observation"))
    if isinstance(obs0,dict):
        farms=obs0.get("farms",[]) or []
        for p,farm in enumerate(farms):
            farm_to_player[id(farm)]=p

        day=int(obs0.get("day",0) or 0)
        hour=int(obs0.get("hour",0) or 0)
        if anchor is None and day==ANCHOR_DAY and hour==0:
            sides=[]
            for p in (0,1):
                op=plain(getv(state[p],"observation"))
                side,rows=init_anchor_side(op)
                sides.append(side)
                ledgers[p].clear()
                ledgers[p].update(rows)
            anchor={
                "day":day,
                "hour":hour,
                "phase":"pre_market",
                "sides":sides,
            }
    return kg_process_market_original(state,env)


kg_process_market_original=None


def summarize_side(p):
    rows=list(ledgers[p].values())
    for r in rows:
        r["potential_mark"]=r["potential_units_same_basis"]*r["price"]
        r["output_reached_mark"]=r["output_reached_same_basis_units"]*r["price"]
        r["harvested_mark"]=r["harvested_same_basis_units"]*r["price"]
        r["not_reached_mark"]=max(0,r["potential_units_same_basis"]-r["output_reached_same_basis_units"])*r["price"]
        r["reached_unharvested_mark"]=max(0,r["output_reached_same_basis_units"]-r["harvested_same_basis_units"])*r["price"]
    return {
        "committed_mark_anchor_existing_basis":float(anchor["sides"][p]["summary"]["committed_mark_existing_basis"]),
        "anchor_ready_mark":sum(r["initial_ready_units"]*r["price"] for r in rows),
        "output_reached_mark_same_basis":sum(r["output_reached_mark"] for r in rows),
        "harvested_mark_same_basis":sum(r["harvested_mark"] for r in rows),
        "not_reached_mark_same_basis":sum(r["not_reached_mark"] for r in rows),
        "reached_unharvested_mark_same_basis":sum(r["reached_unharvested_mark"] for r in rows),
        "extra_output_units_beyond_anchor_basis":sum(r["extra_output_units_beyond_anchor_basis"] for r in rows),
        "asset_count":len(rows),
        "active_asset_count_at_terminal":sum(1 for r in rows if r["active"]),
        "assets":rows,
    }


def main():
    global anchor,main_calls,current_player,current_day,current_hour,kg_process_market_original
    configure()
    anchor=None
    ledgers[0].clear();ledgers[1].clear();farm_to_player.clear();day_start_seen.clear()
    main_calls=0;current_player=None;current_day=None;current_hour=None

    kg._apply_unit_action=wrapped_apply
    kg._daily_refresh_plants=wrapped_refresh_plants
    kg._daily_refresh_animals=wrapped_refresh_animals
    kg_process_market_original=kg._process_market
    kg._process_market=measured_market

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=body_only.agent
        env.run(players)
    finally:
        kg._apply_unit_action=_original_apply
        kg._daily_refresh_plants=_original_refresh_plants
        kg._daily_refresh_animals=_original_refresh_animals
        kg._process_market=kg_process_market_original

    if anchor is None:
        raise SystemExit("Day20 h0 pre-market anchor not captured")

    by_player={str(p):summarize_side(p) for p in (0,1)}
    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.strong-origin-v2.production-downstream-boundary-surface.v0",
        "seed":SEED,
        "seat":SEAT,
        "anchor":{"day":20,"hour":0,"phase":"pre_market","terminal_day":TERMINAL_DAY},
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "by_player":by_player,
        "boundary":[
            "Only productive assets present at the Day20 h0 pre-market anchor are tracked.",
            "All comparison marks use each anchor asset's Day20 displayed product price, matching the anchor Committed Production valuation basis.",
            "output_reached_mark_same_basis credits only anchor-basis units that actually reach the public Output boundary by terminal.",
            "For ongoing crops and animals, post-anchor bonus units beyond the existing base committed basis are recorded separately and do not inflate passage.",
            "For one-time crops, maturity credits at most the anchor potential units actually present when the public first-output boundary is reached.",
            "harvested_mark_same_basis credits HARVEST inventory additions from the same tracked anchor asset, capped by its already-reached same-basis units.",
            "Asset continuity is tracked by coordinate + asset type/class + public origin day and is permanently closed after observed replacement/removal.",
            "This probe stops at Output -> HARVEST/carried. It does not assert carried -> shed -> SELL -> Cash lineage.",
            "No Action motive, product preference, Candidate, or causal explanation is introduced."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    s=by_player[str(SEAT)];o=by_player[str(1-SEAT)]
    print("PRODUCTION_DOWNSTREAM_BOUNDARY_SURFACE "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "self":{k:v for k,v in s.items() if k!="assets"},
        "opponent":{k:v for k,v in o.items() if k!="assets"},
        "terminal":payload["terminal"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
