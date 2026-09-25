"""WR-01 + WR-02 Bundle v0.

WR-01:
- retain native BUY_SEED / BUY_ANIMAL after Day14 only when the purchased asset
  can reach first public Output boundary by season terminal.

WR-02:
- retain native BUY_LAND after Day14 only when self public committed-production
  mark is below opponent at that State.

No new product, quantity, land purchase, or unit action is generated.
BUY_PRODUCT COW remains under baseline D14 closure.
"""
import copy
from collections import Counter

import analyze_sb01_economic_layers_v0 as econ
import strong_origin_body as body
import world_reference_productive_deficit_land_candidate_v0 as wr02

STATIC_COW_TARGETS=((6,2),(10,4),(16,6))
STATIC_FEED_CARRY=3
D14_START_DAY=14
TERMINAL_DAY=econ.SEASON_DAYS

_state={}


def reset_telemetry():
    global _state
    body.COW_TARGETS=STATIC_COW_TARGETS
    body.FEED_CARRY=STATIC_FEED_CARRY
    body.set_reentry_context({})
    body.reset_telemetry()
    _state={
        "turns":0,
        "wr01_reopened_orders":0,
        "wr02_reopened_land_orders":0,
        "wr01_by_key":Counter(),
        "events":[],
    }


def _key(order):
    op=order[0] if order else "UNKNOWN"
    item=order[1] if len(order)>1 else None
    return f"{op}:{item}" if item is not None else op


def _reachable(order,day):
    if not isinstance(order,(list,tuple)) or len(order)<2:
        return False
    op,item=order[0],order[1]
    if op=="BUY_SEED" and item in econ.CROPS:
        return day+int(econ.CROPS[item]["first"])<=TERMINAL_DAY
    if op=="BUY_ANIMAL" and item in econ.ANIMALS:
        return day+int(econ.ANIMALS[item]["first"])<=TERMINAL_DAY
    return False


def _apply(obs,action):
    if not isinstance(action,dict):
        return action,[],[],None
    day=int(obs.get("day",0) or 0)
    if day<D14_START_DAY:
        return action,[],[],None

    player=int(obs["player"])
    self_mark=wr02._public_committed_mark(obs,player)
    opp_mark=wr02._public_committed_mark(obs,1-player)
    deficit=opp_mark-self_mark

    market=list(action.get("market",[]) or [])
    kept=[]; wr01=[]; wr02_land=[]
    for order in market:
        if not isinstance(order,(list,tuple)) or not order:
            kept.append(order); continue
        op=order[0]
        if op in ("BUY_SEED","BUY_ANIMAL"):
            if _reachable(order,day):
                kept.append(order); wr01.append(copy.deepcopy(order))
            continue
        if op=="BUY_LAND":
            if deficit>0:
                kept.append(order); wr02_land.append(copy.deepcopy(order))
            continue
        if op=="BUY_PRODUCT" and len(order)>1 and order[1]=="COW":
            continue
        kept.append(order)

    revised=action
    if kept!=market:
        revised=copy.deepcopy(action); revised["market"]=kept
    event=None
    if wr01 or wr02_land:
        event={
            "day":day,
            "hour":int(obs.get("hour",0) or 0),
            "production_residual":deficit,
            "wr01_reopened":copy.deepcopy(wr01),
            "wr02_reopened_land":copy.deepcopy(wr02_land),
        }
    return revised,wr01,wr02_land,event


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()
    body.COW_TARGETS=STATIC_COW_TARGETS
    body.FEED_CARRY=STATIC_FEED_CARRY
    body.set_reentry_context({})
    native=body.agent(obs)
    action,wr01,wr02_land,event=_apply(obs,native)
    _state["turns"]+=1
    _state["wr01_reopened_orders"]+=len(wr01)
    _state["wr02_reopened_land_orders"]+=len(wr02_land)
    for order in wr01:
        _state["wr01_by_key"][_key(order)]+=1
    if event is not None:
        _state["events"].append(event)
    return action


def get_telemetry():
    out=dict(body.get_telemetry())
    out.update({
        "wr_bundle_v0":True,
        "turns":_state.get("turns",0),
        "wr01_reopened_orders":_state.get("wr01_reopened_orders",0),
        "wr02_reopened_land_orders":_state.get("wr02_reopened_land_orders",0),
        "wr01_by_key":dict(_state.get("wr01_by_key",{})),
        "events":list(_state.get("events",[])),
    })
    return out
