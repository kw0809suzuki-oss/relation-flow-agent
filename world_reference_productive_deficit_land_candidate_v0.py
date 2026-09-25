"""World Reference Productive-Deficit Land Candidate v0 (WR-02).

Connects one observed World-side gap to one model boundary.

Baseline Body-only suppresses all BUY_LAND from Day14 onward.
WR-02 does not create BUY_LAND. It only preserves a native BUY_LAND order when,
at that same public State, self committed-production mark is below opponent.

All crop/animal valuation uses the existing public Economic Layers basis.
BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW remain under baseline D14 closure.
"""
import copy
from collections import Counter

import analyze_sb01_economic_layers_v0 as econ
import strong_origin_body as body

STATIC_COW_TARGETS=((6,2),(10,4),(16,6))
STATIC_FEED_CARRY=3
D14_START_DAY=14

_state={}


def reset_telemetry():
    global _state
    body.COW_TARGETS=STATIC_COW_TARGETS
    body.FEED_CARRY=STATIC_FEED_CARRY
    body.set_reentry_context({})
    body.reset_telemetry()
    _state={
        "turns":0,
        "reopened_land_orders":0,
        "suppressed_land_orders":0,
        "removed_other_d14_orders":0,
        "events":[],
    }


def _public_committed_mark(obs,player):
    farm=obs["farms"][player]
    prices=(obs.get("market",{}) or {}).get("prices",{}) or {}
    day=int(obs.get("day",0) or 0)
    total=0.0
    for row in farm.get("tiles",[]) or []:
        for tile in row or []:
            if not isinstance(tile,dict):
                continue
            crop=tile.get("crop")
            if crop in econ.CROPS:
                rule=econ.CROPS[crop]
                if rule["ongoing"]:
                    _,_,potential=econ._ongoing_crop_remaining(tile,day,rule)
                else:
                    _,_,potential=econ._nonongoing_crop_remaining(tile,day,rule)
                total+=potential*float(prices.get(crop,0) or 0)
            animal=tile.get("animal")
            if animal in econ.ANIMALS:
                rule=econ.ANIMALS[animal]
                _,_,potential=econ._animal_remaining(tile,day,rule)
                total+=potential*float(prices.get(rule["product"],0) or 0)
    return total


def _apply(obs,action):
    if not isinstance(action,dict):
        return action,[],[],None
    day=int(obs.get("day",0) or 0)
    if day<D14_START_DAY:
        return action,[],[],None

    player=int(obs["player"])
    self_mark=_public_committed_mark(obs,player)
    opp_mark=_public_committed_mark(obs,1-player)
    deficit=opp_mark-self_mark

    market=list(action.get("market",[]) or [])
    kept=[]; reopened=[]; removed=[]
    for order in market:
        if not isinstance(order,(list,tuple)) or not order:
            kept.append(order); continue
        op=order[0]
        if op=="BUY_LAND":
            if deficit>0:
                kept.append(order)
                reopened.append(copy.deepcopy(order))
            else:
                removed.append(copy.deepcopy(order))
            continue
        if op in ("BUY_SEED","BUY_ANIMAL"):
            removed.append(copy.deepcopy(order)); continue
        if op=="BUY_PRODUCT" and len(order)>1 and order[1]=="COW":
            removed.append(copy.deepcopy(order)); continue
        kept.append(order)

    revised=action
    if kept!=market:
        revised=copy.deepcopy(action)
        revised["market"]=kept

    event=None
    if reopened or any(o and o[0]=="BUY_LAND" for o in removed):
        event={
            "day":day,
            "hour":int(obs.get("hour",0) or 0),
            "self_committed_mark":self_mark,
            "opponent_committed_mark":opp_mark,
            "residual_opponent_minus_self":deficit,
            "reopened_land":len(reopened),
            "suppressed_land":sum(1 for o in removed if o and o[0]=="BUY_LAND"),
        }
    return revised,reopened,removed,event


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()
    body.COW_TARGETS=STATIC_COW_TARGETS
    body.FEED_CARRY=STATIC_FEED_CARRY
    body.set_reentry_context({})

    native=body.agent(obs)
    action,reopened,removed,event=_apply(obs,native)
    _state["turns"]+=1
    _state["reopened_land_orders"]+=len(reopened)
    _state["suppressed_land_orders"]+=sum(1 for o in removed if o and o[0]=="BUY_LAND")
    _state["removed_other_d14_orders"]+=sum(1 for o in removed if o and o[0]!="BUY_LAND")
    if event is not None:
        _state["events"].append(event)
    return action


def get_telemetry():
    out=dict(body.get_telemetry())
    out.update({
        "wr02_productive_deficit_land":True,
        **_state,
    })
    return out
