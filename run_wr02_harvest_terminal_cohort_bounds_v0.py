#!/usr/bin/env python3
"""WR-02 Harvest-to-Terminal cohort bounds v0.

Tracks the same Day20 anchor cohort through HARVEST exactly, then bounds how
many harvested cohort units could have been realized by SELL by terminal.

Products are fungible after harvest. Therefore no fake unit identity is
introduced. For each product/side, realized cohort units are bounded from
public conservation accounting:

  lower = max(0, cohort_harvested - nonmarket_outflow - terminal_on_hand)
  upper = min(cohort_harvested, realized_sell_units)

The bounds are exact aggregate feasibility bounds absent unit identity; timing
can only narrow them further. Cash bounds use realized per-unit SELL prices.
Observation only; WR-02 and environment policy are unchanged.
"""
import json
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_production_downstream_boundary_surface_v0 as probe
import run_sb01_exact_cash_flow_v0 as exact
import wr02_same_tile_plant_deconfliction_v0 as wr02

SEED=probe.SEED
SEAT=probe.SEAT
OUT=Path(f"wr02_harvest_terminal_cohort_bounds_v0_{SEED}_seat{SEAT}.json")
PRODUCTS=tuple(econ.PRODUCTS)

unit_increase=[defaultdict(int),defaultdict(int)]
unit_decrease=[defaultdict(int),defaultdict(int)]
market_buy=[defaultdict(int),defaultdict(int)]
market_sell=[defaultdict(int),defaultdict(int)]
sell_prices=[[defaultdict(list) for _ in range(1)][0] for _ in range(2)]
anchor_on_hand=None
terminal_on_hand=None
terminal_shed=None

_orig_probe_apply=probe.wrapped_apply

def qtymap(src):
    src=src if isinstance(src,dict) else {}
    return {k:int(src.get(k,0) or 0) for k in PRODUCTS}

def private_stock(private):
    p=probe.plain(private) or {}
    shed=qtymap(p.get("shed",{}) or {})
    inv={k:0 for k in PRODUCTS}
    for row in p.get("inventories",[]) or []:
        if not isinstance(row,dict):
            continue
        for k in PRODUCTS:
            inv[k]+=int(row.get(k,0) or 0)
    return {
        "shed":shed,
        "carried":inv,
        "on_hand":{k:shed[k]+inv[k] for k in PRODUCTS},
    }

def obs_stock(obs):
    return private_stock((obs or {}).get("private",{}) or {})

def wrapped_apply(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
    active=probe.anchor is not None and int(day)>=probe.ANCHOR_DAY
    before=private_stock(private)["on_hand"] if active else None
    _orig_probe_apply(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)
    if not active:
        return
    p=probe.farm_to_player.get(id(farm),probe.current_player)
    if p not in (0,1):
        return
    after=private_stock(private)["on_hand"]
    for item in PRODUCTS:
        d=after[item]-before[item]
        if d>0:
            unit_increase[p][item]+=d
        elif d<0:
            unit_decrease[p][item]+=-d

def capture_anchor_if_needed(state):
    global anchor_on_hand
    obs0=probe.plain(probe.getv(state[0],"observation"))
    if not isinstance(obs0,dict):
        return None
    farms=obs0.get("farms",[]) or []
    for p,farm in enumerate(farms):
        probe.farm_to_player[id(farm)]=p
    day=int(obs0.get("day",0) or 0)
    hour=int(obs0.get("hour",0) or 0)
    if probe.anchor is None and day==probe.ANCHOR_DAY and hour==0:
        sides=[]
        for p in (0,1):
            op=probe.plain(probe.getv(state[p],"observation"))
            side,rows=probe.init_anchor_side(op)
            sides.append(side)
            probe.ledgers[p].clear()
            probe.ledgers[p].update(rows)
        probe.anchor={"day":day,"hour":hour,"phase":"pre_market","sides":sides}
        anchor_on_hand=[obs_stock(probe.plain(probe.getv(state[p],"observation")))["on_hand"] for p in (0,1)]
    return day,hour

def measured_market(state,env):
    global terminal_on_hand,terminal_shed
    ts=capture_anchor_if_needed(state)
    before_n=len(exact.events)
    exact.measured_process_market(state,env)
    if ts is None:
        return
    day,hour=ts
    if probe.anchor is not None and day>=probe.ANCHOR_DAY:
        for e in exact.events[before_n:]:
            p=int(e["player"])
            op=e.get("op")
            item=e.get("item")
            if item not in PRODUCTS:
                continue
            if op=="SELL":
                market_sell[p][item]+=1
                sell_prices[p][item].append(float(e["price"]))
            elif op=="BUY_PRODUCT":
                market_buy[p][item]+=1
        terminal_on_hand=[]
        terminal_shed=[]
        for p in (0,1):
            st=obs_stock(probe.plain(probe.getv(state[p],"observation")))
            terminal_on_hand.append(st["on_hand"])
            terminal_shed.append(st["shed"])

def cohort_by_product(p):
    out=defaultdict(lambda:{"units":0,"mark":0.0,"prices":set()})
    for row in probe.ledgers[p].values():
        q=int(row["harvested_same_basis_units"])
        if q<=0:
            continue
        item=row["product"]
        price=float(row["price"])
        out[item]["units"]+=q
        out[item]["mark"]+=q*price
        out[item]["prices"].add(price)
    result={}
    for item,v in out.items():
        result[item]={
            "units":v["units"],
            "mark":v["mark"],
            "anchor_unit_prices":sorted(v["prices"]),
        }
    return result

def cash_extreme(prices,n,highest):
    n=max(0,min(int(n),len(prices)))
    if n==0:
        return 0.0
    xs=sorted(float(x) for x in prices)
    chosen=xs[-n:] if highest else xs[:n]
    return sum(chosen)

def side_bounds(p):
    cohort=cohort_by_product(p)
    items={}
    total_harvest_mark=0.0
    total_sell_mark_lo=0.0
    total_sell_mark_hi=0.0
    total_cash_lo=0.0
    total_cash_hi=0.0
    conservation={}
    for item in PRODUCTS:
        c=int(cohort.get(item,{}).get("units",0))
        if c<=0:
            continue
        prices0=cohort[item]["anchor_unit_prices"]
        if len(prices0)!=1:
            raise SystemExit(f"Expected one Day20 anchor price for {item}, got {prices0}")
        anchor_price=float(prices0[0])
        i0=int(anchor_on_hand[p][item])
        h=int(unit_increase[p][item])
        k=int(unit_decrease[p][item])
        b=int(market_buy[p][item])
        s=int(market_sell[p][item])
        e=int(terminal_on_hand[p][item])
        err=i0+h+b-s-k-e
        conservation[item]=err
        lo=max(0,c-k-e)
        hi=min(c,s)
        if lo>hi:
            raise SystemExit(f"Infeasible cohort bounds seed={SEED} p={p} item={item}: lo={lo} hi={hi} c={c} k={k} e={e} s={s}")
        sold_mark_lo=lo*anchor_price
        sold_mark_hi=hi*anchor_price
        cp=sell_prices[p][item]
        cash_lo=cash_extreme(cp,lo,False)
        cash_hi=cash_extreme(cp,hi,True)
        items[item]={
            "cohort_harvested_units":c,
            "cohort_harvested_anchor_mark":c*anchor_price,
            "anchor_unit_price":anchor_price,
            "anchor_on_hand_units":i0,
            "all_unit_action_inflow_units":h,
            "all_nonmarket_outflow_units":k,
            "market_buy_units":b,
            "realized_sell_units_all_sources":s,
            "terminal_on_hand_units_all_sources":e,
            "terminal_shed_units_all_sources":int(terminal_shed[p][item]),
            "cohort_realized_sell_units_bound":[lo,hi],
            "cohort_realized_sell_anchor_mark_bound":[sold_mark_lo,sold_mark_hi],
            "cohort_realized_cash_bound":[cash_lo,cash_hi],
            "conservation_error":err,
        }
        total_harvest_mark+=c*anchor_price
        total_sell_mark_lo+=sold_mark_lo
        total_sell_mark_hi+=sold_mark_hi
        total_cash_lo+=cash_lo
        total_cash_hi+=cash_hi
    return {
        "items":items,
        "cohort_harvested_anchor_mark":total_harvest_mark,
        "cohort_realized_sell_anchor_mark_bound":[total_sell_mark_lo,total_sell_mark_hi],
        "cohort_realized_cash_bound":[total_cash_lo,total_cash_hi],
        "conservation_error_by_item":conservation,
    }

def main():
    global anchor_on_hand,terminal_on_hand,terminal_shed
    basecfg._configure_baseline()
    probe.body_only=wr02
    wr02.reset_telemetry()
    probe.anchor=None
    probe.ledgers[0].clear();probe.ledgers[1].clear();probe.farm_to_player.clear();probe.day_start_seen.clear()
    probe.main_calls=0;probe.current_player=None;probe.current_day=None;probe.current_hour=None
    anchor_on_hand=None;terminal_on_hand=None;terminal_shed=None
    for p in (0,1):
        unit_increase[p].clear();unit_decrease[p].clear();market_buy[p].clear();market_sell[p].clear();sell_prices[p].clear()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    probe.wrapped_apply=wrapped_apply
    kg._apply_unit_action=wrapped_apply
    kg._daily_refresh_plants=probe.wrapped_refresh_plants
    kg._daily_refresh_animals=probe.wrapped_refresh_animals
    original_market=kg._process_market
    kg._process_market=measured_market
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=wr02.agent
        env.run(players)
    finally:
        kg._apply_unit_action=probe._original_apply
        kg._daily_refresh_plants=probe._original_refresh_plants
        kg._daily_refresh_animals=probe._original_refresh_animals
        kg._process_market=original_market
        probe.wrapped_apply=_orig_probe_apply

    if probe.anchor is None or anchor_on_hand is None or terminal_on_hand is None:
        raise SystemExit("Missing anchor or terminal stock capture")
    rewards=[float(x.reward) for x in env.state]
    by_player={str(p):side_bounds(p) for p in (0,1)}
    payload={
        "schema":"kaggriculture.strong-origin-v2.wr02-harvest-terminal-cohort-bounds.v0",
        "seed":SEED,"seat":SEAT,
        "active_model":"Baseline+WR-02",
        "anchor":{"day":20,"hour":0,"phase":"pre_market"},
        "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
        "by_player":by_player,
        "boundary":[
            "Day20 anchor assets and HARVEST passage reuse the existing validated cohort accounting.",
            "After HARVEST, product units are fungible in public State; exact cohort identity is not asserted.",
            "Realized cohort SELL is therefore reported as conservation-feasible lower/upper bounds, not a fabricated exact lineage.",
            "Lower bound allocates cohort units first to observed nonmarket outflow and terminal on-hand stock; upper bound is min(cohort harvested, all realized SELL units).",
            "Cash bounds use the lowest lower-bound-count and highest upper-bound-count realized unit SELL prices for each product; timing can narrow these bounds but cannot justify a point estimate here.",
            "No Candidate, Action diagnosis, policy change, or adoption decision is introduced."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WR02_HARVEST_TERMINAL_COHORT_BOUNDS "+json.dumps({
        "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
        "self":by_player[str(SEAT)],
        "opponent":by_player[str(1-SEAT)]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
