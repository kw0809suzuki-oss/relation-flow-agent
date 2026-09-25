"""World Reference Reachability Candidate v0.

Purpose:
Connect one confirmed World-side fact to the model without choosing products
or prescribing an action.

Baseline Body-only has a fixed Day14 expansion closure. This candidate keeps
the native model's own BUY_SEED / BUY_ANIMAL choices after Day14 only when the
purchased productive asset could reach its first public Output boundary by
season terminal under the public schedule.

Unchanged:
- native crop/animal choice
- native quantity
- unit actions
- SELL/HIRE/feed behavior
- BUY_LAND remains closed from Day14
- BUY_PRODUCT COW remains closed from Day14
"""
import copy
from collections import Counter

import analyze_sb01_economic_layers_v0 as econ
import strong_origin_body as body

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
        "changed_turns":0,
        "reopened_orders":0,
        "removed_orders":0,
        "reopened_by_key":Counter(),
        "removed_by_key":Counter(),
        "events":[],
    }


def _key(order):
    if not isinstance(order,(list,tuple)) or not order:
        return "UNKNOWN"
    op=order[0]
    item=order[1] if len(order)>1 else None
    return f"{op}:{item}" if item is not None else op


def _productive_reachable(order,day):
    if not isinstance(order,(list,tuple)) or len(order)<2:
        return False,None
    op,item=order[0],order[1]
    if op=="BUY_SEED" and item in econ.CROPS:
        first=int(econ.CROPS[item]["first"])
        return day+first<=TERMINAL_DAY,first
    if op=="BUY_ANIMAL" and item in econ.ANIMALS:
        first=int(econ.ANIMALS[item]["first"])
        return day+first<=TERMINAL_DAY,first
    return False,None


def _apply_world_reference_gate(obs,action):
    if not isinstance(action,dict):
        return action,[],[]
    day=int(obs.get("day",0) or 0)
    if day<D14_START_DAY:
        return action,[],[]

    market=list(action.get("market",[]) or [])
    kept=[]
    reopened=[]
    removed=[]

    for order in market:
        if not isinstance(order,(list,tuple)) or not order:
            kept.append(order)
            continue
        op=order[0]

        if op in ("BUY_SEED","BUY_ANIMAL"):
            reachable,first=_productive_reachable(order,day)
            if reachable:
                kept.append(order)
                reopened.append({
                    "order":copy.deepcopy(order),
                    "day":day,
                    "first_output_delay_days":first,
                    "latest_first_output_day":day+first,
                    "terminal_day":TERMINAL_DAY,
                })
            else:
                removed.append(copy.deepcopy(order))
            continue

        # Preserve the adopted fixed closure for surfaces not yet connected
        # to the World reference in this candidate.
        if op=="BUY_LAND":
            removed.append(copy.deepcopy(order))
            continue
        if op=="BUY_PRODUCT" and len(order)>1 and order[1]=="COW":
            removed.append(copy.deepcopy(order))
            continue

        kept.append(order)

    if kept==market:
        return action,reopened,removed
    revised=copy.deepcopy(action)
    revised["market"]=kept
    return revised,reopened,removed


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()

    body.COW_TARGETS=STATIC_COW_TARGETS
    body.FEED_CARRY=STATIC_FEED_CARRY
    body.set_reentry_context({})

    native=body.agent(obs)
    action,reopened,removed=_apply_world_reference_gate(obs,native)

    _state["turns"]+=1
    if reopened or removed:
        _state["changed_turns"]+=1
    _state["reopened_orders"]+=len(reopened)
    _state["removed_orders"]+=len(removed)
    for row in reopened:
        _state["reopened_by_key"][_key(row["order"])]+=1
    for order in removed:
        _state["removed_by_key"][_key(order)]+=1
    if reopened or removed:
        _state["events"].append({
            "day":int(obs.get("day",0) or 0),
            "hour":int(obs.get("hour",0) or 0),
            "reopened":reopened,
            "removed":removed,
        })
    return action


def get_telemetry():
    out=dict(body.get_telemetry())
    out.update({
        "world_reference_reachability_candidate_v0":True,
        "d14_start_day":D14_START_DAY,
        "terminal_day":TERMINAL_DAY,
        "turns":_state.get("turns",0),
        "changed_turns":_state.get("changed_turns",0),
        "reopened_orders":_state.get("reopened_orders",0),
        "removed_orders":_state.get("removed_orders",0),
        "reopened_by_key":dict(_state.get("reopened_by_key",{})),
        "removed_by_key":dict(_state.get("removed_by_key",{})),
        "events":list(_state.get("events",[])),
    })
    return out
