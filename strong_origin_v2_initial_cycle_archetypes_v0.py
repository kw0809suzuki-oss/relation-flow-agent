"""Strong Origin v2 initial-cycle archetypes v0.

All modes preserve Body-only v0 after Day4 and share the same Day0-4
work-target reservation substrate so the comparison is about the economic
starting state rather than duplicate-target coordination.

Modes:
- FAST_CLOSURE: same early productive target count, WHEAT-only, no early LAND/animal.
- PRODUCTIVE_OCCUPANCY: fill existing unlocked capacity before expanding it.
- CAPITAL_PRESERVATION: keep at least half of observed opening Cash through Day4.
- ANIMAL_CYCLE: COW-first productive lane plus a small WHEAT support crop lane.

This is an experiment bundle, not an adoption candidate.
"""
import copy
import os

import strong_origin_body
import strong_origin_v2_body_only_v0 as body_only
import strong_origin_early_target_reservation_v0 as early_origin

MODES=("FAST_CLOSURE","PRODUCTIVE_OCCUPANCY","CAPITAL_PRESERVATION","ANIMAL_CYCLE")
EARLY_END_DAY=4
CAPITAL_FLOOR_FRACTION=0.50
ANIMAL_TARGET_COWS=4
ANIMAL_CASH_FLOOR=600.0

_state={}


def _fib(n):
    a,b=1,1
    for _ in range(n):
        a,b=b,a+b
    return a


def _mode():
    m=os.getenv("INITIAL_CYCLE_MODE","FAST_CLOSURE").strip().upper()
    if m not in MODES:
        raise ValueError(f"Unknown INITIAL_CYCLE_MODE={m}")
    return m


def _call_with_origin(fn,*args,**kwargs):
    old=strong_origin_body.strong_origin
    strong_origin_body.strong_origin=early_origin
    try:
        return fn(*args,**kwargs)
    finally:
        strong_origin_body.strong_origin=old


def reset_telemetry():
    global _state
    _state={
        "mode":_mode(),
        "opening_cash":None,
        "changed_turns":0,
        "removed_orders":0,
        "added_orders":0,
        "early_turns":0,
    }
    return _call_with_origin(body_only.reset_telemetry)


def _target_fn(mode, original):
    def targets(name,day,capacity):
        base=original(name,day,capacity)
        if int(day)>EARLY_END_DAY:
            return base
        if mode=="FAST_CLOSURE":
            total=max(1,sum(int(v) for v in base.values()))
            return {"WHEAT":total,"MELON":0,"STRAWBERRY":0}
        if mode=="PRODUCTIVE_OCCUPANCY":
            total=max(1,int(capacity))
            wheat=(total+1)//2
            return {"WHEAT":wheat,"MELON":total-wheat,"STRAWBERRY":0}
        if mode=="ANIMAL_CYCLE":
            wheat=max(8,int(round(capacity*0.35)))
            return {"WHEAT":wheat,"MELON":0,"STRAWBERRY":0}
        return base
    return targets


def _is_order(order,op,item=None):
    if not isinstance(order,(list,tuple)) or not order or order[0]!=op:
        return False
    return item is None or (len(order)>1 and order[1]==item)


def _count_cows(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    private=obs.get("private",{}) or {}
    n=int((private.get("shed",{}) or {}).get("COW",0) or 0)
    for inv in private.get("inventories",[]) or []:
        n+=int((inv or {}).get("COW",0) or 0)
    for row in me.get("tiles",[]) or []:
        for t in row or []:
            if isinstance(t,dict) and t.get("animal")=="COW":
                n+=1
    return n


def _capital_preservation_market(obs,market):
    p=int(obs["player"])
    me=obs["farms"][p]
    prices=(obs.get("market",{}) or {}).get("prices",{}) or {}
    opening=float(_state.get("opening_cash") or me.get("money",0) or 0)
    floor=opening*CAPITAL_FLOOR_FRACTION
    projected=float(me.get("money",0) or 0)
    hires=int(me.get("hires_today",0) or 0)
    quadrants=len(me.get("unlocked_quadrants",[]) or [])
    animal_cost={"GOOSE":300,"COW":400,"SHEEP":500}
    seed_cost={"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
    kept=[]
    removed=[]
    for o in market:
        if not isinstance(o,(list,tuple)) or not o:
            kept.append(o); continue
        op=o[0]
        if op=="SELL":
            kept.append(o)
            continue
        cost=0.0
        if op=="HIRE":
            cost=float(_fib(hires)); hires+=1
        elif op=="BUY_LAND":
            cost=float({1:1000,2:2000,3:4000}.get(quadrants,10**9))
            quadrants+=1
        elif op=="BUY_SEED" and len(o)>=3:
            cost=float(seed_cost.get(o[1],10**9))*int(o[2])
        elif op=="BUY_ANIMAL" and len(o)>=3:
            cost=float(animal_cost.get(o[1],10**9))*int(o[2])
        elif op=="BUY_PRODUCT" and len(o)>=3:
            cost=float(prices.get(o[1],0) or 0)*int(o[2])*1.10
        if projected-cost>=floor:
            kept.append(o); projected-=cost
        else:
            removed.append(copy.deepcopy(o))
    return kept,removed


def _apply_mode(obs,action,mode):
    if not isinstance(action,dict):
        return action,[],[]
    day=int(obs.get("day",0) or 0)
    if day>EARLY_END_DAY:
        return action,[],[]
    revised=copy.deepcopy(action)
    market=list(revised.get("market",[]) or [])
    removed=[]
    added=[]

    if mode=="FAST_CLOSURE":
        keep=[]
        for o in market:
            if _is_order(o,"BUY_LAND") or _is_order(o,"BUY_ANIMAL") or (
                _is_order(o,"BUY_SEED") and len(o)>1 and o[1]!="WHEAT"
            ):
                removed.append(copy.deepcopy(o))
            else:
                keep.append(o)
        market=keep

    elif mode=="PRODUCTIVE_OCCUPANCY":
        keep=[]
        for o in market:
            if _is_order(o,"BUY_LAND"):
                removed.append(copy.deepcopy(o))
            else:
                keep.append(o)
        market=keep

    elif mode=="CAPITAL_PRESERVATION":
        market,removed=_capital_preservation_market(obs,market)

    elif mode=="ANIMAL_CYCLE":
        keep=[]
        for o in market:
            if _is_order(o,"BUY_LAND") or (
                _is_order(o,"BUY_SEED") and len(o)>1 and o[1]!="WHEAT"
            ):
                removed.append(copy.deepcopy(o))
            else:
                keep.append(o)
        market=keep
        cows=_count_cows(obs)
        me=obs["farms"][int(obs["player"])]
        has_cow_buy=any(_is_order(o,"BUY_ANIMAL","COW") for o in market)
        if cows<ANIMAL_TARGET_COWS and not has_cow_buy and float(me.get("money",0) or 0)-400>=ANIMAL_CASH_FLOOR and len(market)<10:
            order=["BUY_ANIMAL","COW",1]
            insert_at=0
            while insert_at<len(market) and _is_order(market[insert_at],"SELL"):
                insert_at+=1
            market.insert(insert_at,order)
            added.append(order)

    revised["market"]=market[:10]
    return revised,removed,added


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()
    mode=_mode()
    if _state.get("opening_cash") is None:
        p=int(obs["player"])
        _state["opening_cash"]=float(obs["farms"][p].get("money",0) or 0)

    original_targets=early_origin.origin_targets
    early_origin.origin_targets=_target_fn(mode,original_targets)
    try:
        action=_call_with_origin(body_only.agent,obs)
    finally:
        early_origin.origin_targets=original_targets

    revised,removed,added=_apply_mode(obs,action,mode)
    if int(obs.get("day",0) or 0)<=EARLY_END_DAY:
        _state["early_turns"]+=1
    if removed or added or revised!=action:
        _state["changed_turns"]+=1
    _state["removed_orders"]+=len(removed)
    _state["added_orders"]+=len(added)
    return revised


def get_telemetry():
    out=dict(body_only.get_telemetry())
    out.update({
        "initial_cycle_archetype":True,
        "early_end_day":EARLY_END_DAY,
        "capital_floor_fraction":CAPITAL_FLOOR_FRACTION,
        "animal_target_cows":ANIMAL_TARGET_COWS,
        **_state,
    })
    return out
