#!/usr/bin/env python3
"""Completion Cash Margin Observer v0.

Same Completion-only candidate, same seeds 7111-7120.
No policy change.

At every post-D14 BUY_SEED decision, observe:
- current cash
- native strategy reserve
- cash margin = money - reserve
- same-turn market cash flow before/through seed orders
- minimum projected cash after each seed order
- seed spend

Purpose:
Test whether Completion-only improved vs worsened cases separate on cash
preservation before defining any cash threshold.
"""

import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import investment_completion_coordinate_v0 as candidate
from strong_origin import (
    BASE_PRICE, STRATEGIES, SEED_COST, fib_hire_cost
)
from x_engine import XField, choose_x_origin

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"completion_cash_margin_v0_{SEED}.json")

def configure_current():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()

def configure_candidate():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    candidate.set_probe_enabled(True)
    candidate.set_attribution_enabled(True)
    candidate.reset_experiment()

def _public_production(farm):
    active=animals=0
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if tile=="LOCKED" or tile is None:
                continue
            active+=1
            if isinstance(tile,dict) and tile.get("animal"):
                animals+=1
    return active+animals

def native_reserve(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    opp=obs["farms"][1-p]
    tiles=me.get("tiles",[]) or []
    unlocked=0
    empty=0
    supply={c:0 for c in BASE_PRICE}
    opp_supply={c:0 for c in BASE_PRICE}
    for row in tiles:
        for tile in row:
            if tile=="LOCKED":
                continue
            unlocked+=1
            if tile is None:
                empty+=1
            elif isinstance(tile,dict) and tile.get("kind")=="PLANT" and tile.get("crop") in supply:
                supply[tile["crop"]]+=1
    for row in opp.get("tiles",[]) or []:
        for tile in row:
            if isinstance(tile,dict) and tile.get("kind")=="PLANT" and tile.get("crop") in opp_supply:
                opp_supply[tile["crop"]]+=1

    day=int(obs.get("day",0) or 0)
    field=XField(
        day=day,
        remaining_days=30-day,
        my_money=me.get("money",0),
        opp_money=opp.get("money",0),
        my_land=len(me.get("unlocked_quadrants",[]) or []),
        opp_land=len(opp.get("unlocked_quadrants",[]) or []),
        my_hands=len(me.get("hands",[]) or []),
        opp_hands=len(opp.get("hands",[]) or []),
        prices=(obs.get("market",{}) or {}).get("prices",{}) or {},
        my_supply=supply,
        opp_supply=opp_supply,
    )
    strategy=choose_x_origin(field,BASE_PRICE).origin
    occupied=unlocked-empty
    reserve=float(STRATEGIES[strategy]["reserve_base"] + 20*occupied)
    return strategy,reserve

def is_seed(a):
    return isinstance(a,(list,tuple)) and len(a)>=3 and a[0]=="BUY_SEED"

def market_projection(obs,market):
    prices=(obs.get("market",{}) or {}).get("prices",{}) or {}
    cash=float(obs["farms"][obs["player"]].get("money",0) or 0)
    hires=int(obs["farms"][obs["player"]].get("hires_today",0) or 0)
    seed_spend=0.0
    sell_cash=0.0
    min_after_seed=None
    seed_steps=[]
    unknown=[]

    for idx,a in enumerate(market):
        if not isinstance(a,(list,tuple)) or not a:
            continue
        op=a[0]
        before=cash
        if op=="SELL" and len(a)>=3:
            value=float(prices.get(a[1],0) or 0)*float(a[2] or 0)
            cash+=value
            sell_cash+=value
        elif op=="BUY_SEED" and len(a)>=3:
            cost=float(SEED_COST.get(a[1],0) or 0)*float(a[2] or 0)
            cash-=cost
            seed_spend+=cost
            min_after_seed=cash if min_after_seed is None else min(min_after_seed,cash)
            seed_steps.append({
                "index":idx,"crop":a[1],"qty":a[2],
                "before_cash":before,"cost":cost,"after_cash":cash
            })
        elif op=="BUY_PRODUCT" and len(a)>=3:
            cash-=float(prices.get(a[1],0) or 0)*float(a[2] or 0)
        elif op=="BUY_ANIMAL" and len(a)>=3:
            # Current Completion candidate should suppress COW after D14.
            cost=400.0*float(a[2] or 0) if a[1]=="COW" else 0.0
            cash-=cost
        elif op=="HIRE":
            cost=float(fib_hire_cost(hires))
            cash-=cost
            hires+=1
        else:
            unknown.append(copy.deepcopy(a))
    return {
        "sell_cash":sell_cash,
        "seed_spend":seed_spend,
        "projected_end_cash":cash,
        "min_after_seed_cash":min_after_seed,
        "seed_steps":seed_steps,
        "unknown_orders":unknown,
    }

def play(mode):
    if mode=="baseline": configure_current()
    else: configure_candidate()

    decisions=[]
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        action=current.agent(obs) if mode=="baseline" else candidate.agent(obs)
        day=int(obs.get("day",0) or 0)
        if mode=="candidate" and day>=14 and isinstance(action,dict):
            market=list(action.get("market",[]) or [])
            if any(is_seed(a) for a in market):
                strategy,reserve=native_reserve(obs)
                money=float(obs["farms"][obs["player"]].get("money",0) or 0)
                proj=market_projection(obs,market)
                min_after=proj["min_after_seed_cash"]
                decisions.append({
                    "day":day,
                    "money":money,
                    "strategy":strategy,
                    "native_reserve":reserve,
                    "cash_margin":money-reserve,
                    "cash_to_reserve":(money/reserve) if reserve>0 else None,
                    "post_seed_margin":(min_after-reserve) if min_after is not None else None,
                    "post_seed_to_reserve":(min_after/reserve) if min_after is not None and reserve>0 else None,
                    "market":copy.deepcopy(market),
                    **proj,
                })
        return action

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"self":rewards[SEAT],"opp":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"decisions":decisions}

def summarize(rows):
    out={"count":len(rows)}
    keys=["money","native_reserve","cash_margin","cash_to_reserve","post_seed_margin","post_seed_to_reserve","seed_spend","sell_cash","projected_end_cash","min_after_seed_cash"]
    for k in keys:
        vals=[r.get(k) for r in rows if isinstance(r.get(k),(int,float))]
        if vals:
            out["mean_"+k]=sum(vals)/len(vals)
            out["min_"+k]=min(vals)
            out["max_"+k]=max(vals)
    out["total_seed_spend"]=sum(float(r.get("seed_spend",0) or 0) for r in rows)
    return out

def main():
    b=play("baseline")
    c=play("candidate")
    diff=c["self"]-b["self"]
    payload={
        "schema":"kaggriculture.completion-cash-margin.v0",
        "seed":SEED,"seat":SEAT,
        "baseline_self":b["self"],
        "candidate_self":c["self"],
        "self_diff":diff,
        "direction":"improved" if diff>0 else "worsened" if diff<0 else "equal",
        "candidate_seed_decisions":c["decisions"],
        "candidate_seed_cash_summary":summarize(c["decisions"]),
        "boundary":[
            "Observer only; no policy change.",
            "Same Completion-only candidate and same seeds 7111-7120.",
            "Native reserve is reconstructed from the frozen strong_origin reserve formula and strategy selection.",
            "No cash threshold is defined or promoted.",
            "Purpose is only to test whether improved and worsened cases separate on cash margin / post-seed cash preservation."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMPLETION_CASH_MARGIN_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
