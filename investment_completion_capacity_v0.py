"""Investment Completion + Recovery Capacity Preservation v0.

Goal:
- Keep the full-cycle Completion test from Investment Completion Coordinate v0.
- Add one grounded capacity guard without inventing a new threshold.

Rules after Day14:
- LAND: closed exactly as Current.
- COW: closed exactly as Current.
- SEED: allowed only if:
    1) minimum full Cash Conversion Cycle can finish before terminal, and
    2) native policy is NOT simultaneously asking for HIRE on this turn.
- HIRE / HARVEST / SELL / unit actions remain unchanged.

Interpretation of the guard:
- A native HIRE order is treated as the model's own signal that current labor
  capacity is insufficient for its present workload.
- In that state, do not add new seed commitment.
- Native seed orders have already passed the native cash-reserve check, so no
  duplicate or invented cash threshold is added here.

This tests Completion + Recovery Capacity Preservation only.
"""

import copy
import g17_agent as native
from strong_origin import FIRST_YIELD, MAX_YIELD_DAY

DAY_CALLS=24
TERMINAL_DAY=30
TOTAL_TURNS=DAY_CALLS*TERMINAL_DAY
D14=14

_state={}

def reset_experiment():
    global _state
    _state={
        "turn":0,
        "seed_considered_after_d14":0,
        "seed_allowed":0,
        "seed_removed_incomplete":0,
        "seed_removed_hire_pressure":0,
        "land_removed_d14":0,
        "cow_removed_d14":0,
        "native_hire_signal_turns":0,
        "events":[],
    }
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def _op(a):
    return a[0] if isinstance(a,(list,tuple)) and a else None

def _is_land(a):
    return _op(a)=="BUY_LAND"

def _is_seed(a):
    return _op(a)=="BUY_SEED"

def _seed_crop(a):
    return a[1] if isinstance(a,(list,tuple)) and len(a)>1 else None

def _is_cow(a):
    return (
        _op(a)=="BUY_ANIMAL" and len(a)>1 and a[1]=="COW"
    ) or (
        _op(a)=="BUY_PRODUCT" and len(a)>1 and a[1]=="COW"
    )

def _is_hire(a):
    return _op(a)=="HIRE"

def _shed_cells(board_size):
    h=board_size//2
    return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]

def _min_empty_to_shed(obs):
    me=obs["farms"][obs["player"]]
    tiles=me.get("tiles",[]) or []
    shed=_shed_cells(len(tiles))
    best=None
    for y,row in enumerate(tiles):
        for x,tile in enumerate(row):
            if tile is not None:
                continue
            d=min(abs(x-sx)+abs(y-sy) for sx,sy in shed)
            best=d if best is None else min(best,d)
    return best

def _native_wait_days(crop):
    if crop=="STRAWBERRY":
        return FIRST_YIELD.get(crop)
    return MAX_YIELD_DAY.get(crop)

def _required_turns(obs,crop):
    wait_days=_native_wait_days(crop)
    if wait_days is None:
        return None,None
    transport=_min_empty_to_shed(obs)
    if transport is None:
        return None,None
    required=1 + int(wait_days)*DAY_CALLS + 1 + int(transport) + 1 + 1
    return required,{
        "plant_turns":1,
        "native_wait_days":int(wait_days),
        "native_wait_turns":int(wait_days)*DAY_CALLS,
        "harvest_turns":1,
        "transport_turns":int(transport),
        "drop_turns":1,
        "sell_turns":1,
    }

def agent(obs):
    if not _state:
        reset_experiment()

    turn=_state["turn"]
    _state["turn"]+=1
    remaining_turns=max(0,TOTAL_TURNS-turn)

    actions=native.agent(obs)
    if not isinstance(actions,dict):
        return actions

    day=int(obs.get("day",0) or 0)
    if day < D14:
        return actions

    market=list(actions.get("market",[]) or [])
    hire_pressure=any(_is_hire(a) for a in market)
    if hire_pressure:
        _state["native_hire_signal_turns"]+=1

    revised=[]
    changes=[]

    for a in market:
        if _is_land(a):
            _state["land_removed_d14"]+=1
            changes.append({"kind":"remove","reason":"land_d14","day":day,"turn":turn,"action":copy.deepcopy(a)})
            continue

        if _is_cow(a):
            _state["cow_removed_d14"]+=1
            changes.append({"kind":"remove","reason":"cow_d14","day":day,"turn":turn,"action":copy.deepcopy(a)})
            continue

        if _is_seed(a):
            _state["seed_considered_after_d14"]+=1
            crop=_seed_crop(a)
            required,parts=_required_turns(obs,crop)
            completion_ok=(required is not None and required < remaining_turns)

            if not completion_ok:
                _state["seed_removed_incomplete"]+=1
                changes.append({
                    "kind":"remove",
                    "reason":"full_cycle_incomplete",
                    "day":day,"turn":turn,
                    "remaining_turns":remaining_turns,
                    "required_turns":required,
                    "crop":crop,
                    "hire_pressure":hire_pressure,
                    "parts":parts,
                    "action":copy.deepcopy(a),
                })
                continue

            if hire_pressure:
                _state["seed_removed_hire_pressure"]+=1
                changes.append({
                    "kind":"remove",
                    "reason":"preserve_recovery_capacity",
                    "day":day,"turn":turn,
                    "remaining_turns":remaining_turns,
                    "required_turns":required,
                    "crop":crop,
                    "hire_pressure":True,
                    "parts":parts,
                    "action":copy.deepcopy(a),
                })
                continue

            _state["seed_allowed"]+=1
            revised.append(a)
            changes.append({
                "kind":"allow",
                "reason":"full_cycle_and_capacity_ok",
                "day":day,"turn":turn,
                "remaining_turns":remaining_turns,
                "required_turns":required,
                "crop":crop,
                "hire_pressure":False,
                "parts":parts,
                "action":copy.deepcopy(a),
            })
            continue

        revised.append(a)

    if not changes:
        return actions

    out=copy.deepcopy(actions)
    out["market"]=revised
    _state["events"].extend(changes)
    return out

def get_experiment_telemetry():
    return copy.deepcopy(_state)

def get_trace():
    return native.get_trace()
