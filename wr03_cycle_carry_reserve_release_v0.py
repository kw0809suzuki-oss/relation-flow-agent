"""WR-03: Cycle Carry reserve release v0.

World gap:
Generated Return reaches Cash, but self can delay the next productive surface.

Minimal intervention:
- Do not choose LAND, crop, animal, seed, hire, position, or quantity.
- Detect a generated non-WHEAT Return on the live self trajectory.
- Until the next productive occupied tile appears, temporarily release only the
  frozen Origin reserve_base floor so the native Body may reinvest its own way.
- Keep the per-occupied-tile reserve (20 * occupied), all native strategy logic,
  D14 closure, and every native action choice intact.
- Stop immediately when productive occupied tiles increase, or at Day14.

This is a flow bridge, not a Day7/LAND/MELON/WHEAT rule.
"""
import copy

import strong_origin
import strong_origin_v2_body_only_v0 as baseline

RETURN_ITEMS=("MELON","STRAWBERRY","MILK","WOOL","EGG")
D14_START_DAY=baseline.D14_START_DAY

_state={}


def _stock_total(obs,item):
    private=obs.get("private",{}) or {}
    total=int((private.get("shed",{}) or {}).get(item,0) or 0)
    for inv in (private.get("inventories",[]) or []):
        total+=int((inv or {}).get(item,0) or 0)
    return total


def _productive_count(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    n=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if isinstance(t,dict) and (t.get("kind")=="PLANT" or t.get("animal")):
                n+=1
    return n


def _generated_sell_signal(obs):
    # Native Body emits SELL only for stock it currently observes.
    # For these zero-initial / no-BUY_PRODUCT return classes, a prior emitted
    # SELL is a conservative live signal that farm-generated value entered Cash.
    prev_action=_state.get("prev_action") or {}
    prev_stocks=_state.get("prev_stocks") or {}
    signaled=[]
    for order in prev_action.get("market",[]) or []:
        if not isinstance(order,(list,tuple)) or len(order)<2 or order[0]!="SELL":
            continue
        item=order[1]
        if item in RETURN_ITEMS and int(prev_stocks.get(item,0) or 0)>0:
            signaled.append(item)

    # Also catch a visible stock decrease across calls.
    current={i:_stock_total(obs,i) for i in RETURN_ITEMS}
    for item in RETURN_ITEMS:
        if int(prev_stocks.get(item,0) or 0)>current[item]:
            signaled.append(item)
    return sorted(set(signaled)),current


def _with_reserve_release(fn):
    original={name:cfg.get("reserve_base") for name,cfg in strong_origin.STRATEGIES.items()}
    try:
        for cfg in strong_origin.STRATEGIES.values():
            if "reserve_base" in cfg:
                cfg["reserve_base"]=0
        return fn()
    finally:
        for name,value in original.items():
            strong_origin.STRATEGIES[name]["reserve_base"]=value


def reset_telemetry():
    global _state
    baseline.reset_telemetry()
    _state={
        "turns":0,
        "cycle_open":False,
        "anchor_productive_count":None,
        "return_signals":0,
        "active_turns":0,
        "surface_closures":0,
        "d14_closures":0,
        "events":[],
        "prev_action":None,
        "prev_stocks":None,
    }


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()

    day=int(obs.get("day",0) or 0)
    productive=_productive_count(obs)

    signal_items=[]
    if _state["prev_stocks"] is not None:
        signal_items,current_stocks=_generated_sell_signal(obs)
    else:
        current_stocks={i:_stock_total(obs,i) for i in RETURN_ITEMS}

    if _state["cycle_open"]:
        anchor=int(_state["anchor_productive_count"])
        if productive>anchor:
            _state["cycle_open"]=False
            _state["surface_closures"]+=1
            _state["events"].append({
                "day":day,"hour":int(obs.get("hour",0) or 0),
                "event":"productive_surface_reached",
                "anchor_productive_count":anchor,
                "current_productive_count":productive,
            })
        elif day>=D14_START_DAY:
            _state["cycle_open"]=False
            _state["d14_closures"]+=1
            _state["events"].append({
                "day":day,"hour":int(obs.get("hour",0) or 0),
                "event":"closed_by_d14",
                "anchor_productive_count":anchor,
                "current_productive_count":productive,
            })

    if signal_items and day<D14_START_DAY and not _state["cycle_open"]:
        _state["cycle_open"]=True
        _state["anchor_productive_count"]=productive
        _state["return_signals"]+=1
        _state["events"].append({
            "day":day,"hour":int(obs.get("hour",0) or 0),
            "event":"generated_return_open",
            "items":signal_items,
            "anchor_productive_count":productive,
        })

    active=bool(_state["cycle_open"] and day<D14_START_DAY)
    if active:
        _state["active_turns"]+=1
        action=_with_reserve_release(lambda: baseline.agent(obs))
    else:
        action=baseline.agent(obs)

    _state["turns"]+=1
    _state["prev_action"]=copy.deepcopy(action)
    _state["prev_stocks"]=current_stocks
    return action


def get_telemetry():
    out=dict(baseline.get_telemetry())
    out.update({
        "wr03_cycle_carry_reserve_release":True,
        "wr03_return_items":list(RETURN_ITEMS),
        "wr03_d14_preserved":True,
        "wr03_turns":_state.get("turns",0),
        "wr03_return_signals":_state.get("return_signals",0),
        "wr03_active_turns":_state.get("active_turns",0),
        "wr03_surface_closures":_state.get("surface_closures",0),
        "wr03_d14_closures":_state.get("d14_closures",0),
        "wr03_events":list(_state.get("events",[])),
    })
    return out
