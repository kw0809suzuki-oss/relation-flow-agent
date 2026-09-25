"""Phase A Router v0.

Outer-State-only router over the current Active Model (Body + WR-02).

Choice set:
- HOLD
- SURFACE
- THROUGHPUT
- ENGINE

The router chooses once at the first observed turn of each day before Day12 and
holds that direction for the rest of that day. It uses only current self-visible
World State: productive occupancy, workers, cash, and land availability.

No opponent state, seed, terminal reward, future state, or hidden model trace is
used for routing.

Patterns are the already-tested broad Phase A takeoff variants:
- SURFACE: early LAND timing only.
- THROUGHPUT: early HIRE timing only.
- ENGINE: stronger native productive commitment while preserving native crop
  support.
- HOLD: current Active Model unchanged.

WR-02 is always applied last. D14 closure remains unchanged.
"""
from collections import Counter

import strong_origin_v2_body_only_v0 as baseline
import wr02_same_tile_plant_deconfliction_v0 as wr02
import phase_a_takeoff_variants_v0 as variants

PHASE_A_END_DAY=12
HOLD="hold"
SURFACE="surface_first"
THROUGHPUT="throughput_first"
ENGINE="engine_first"

_state={}


def _outer_state(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    productive=0
    unlocked=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if t!="LOCKED":
                unlocked+=1
            if isinstance(t,dict) and (t.get("kind")=="PLANT" or t.get("animal")):
                productive+=1
    workers=1+len(farm.get("hands",[]) or [])
    cash=float(farm.get("money",0) or 0)
    quadrants=len(farm.get("unlocked_quadrants",[]) or [])
    land_cost={1:1000,2:2000,3:4000}.get(quadrants)
    occupancy=productive/max(1,unlocked)
    load=productive/max(1,workers)
    return {
        "productive":productive,
        "unlocked":unlocked,
        "occupancy":occupancy,
        "workers":workers,
        "load_per_worker":load,
        "cash":cash,
        "land_cost":land_cost,
    }


def _route(s):
    # Surface pressure: the current productive surface is already crowded and
    # another surface is actually cash-feasible.
    if (
        s["land_cost"] is not None
        and s["occupancy"]>=0.60
        and s["cash"]-s["land_cost"]>=variants.SURVIVAL_RESERVE
    ):
        return SURFACE

    # Throughput pressure: current productive body is too large for the current
    # worker count. Keep this before Engine so labor saturation is not mistaken
    # for a need to create still more productive commitments.
    if (
        s["workers"]<variants.THROUGHPUT_TARGET_UNITS
        and s["load_per_worker"]>=3.0
        and s["cash"]>=variants.SURVIVAL_RESERVE+1
    ):
        return THROUGHPUT

    # Engine pressure: usable surface remains and labor is not yet the dominant
    # constraint, so enlarge native productive commitment on the current surface.
    if (
        s["occupancy"]<0.75
        and s["cash"]>=variants.SURVIVAL_RESERVE
        and (s["workers"]>=2 or s["load_per_worker"]<3.0)
    ):
        return ENGINE

    return HOLD


def reset_telemetry():
    global _state
    baseline.reset_telemetry()
    wr02._state={
        "turns":0,
        "duplicate_plant_commands_seen":0,
        "deconflicted_to_move":0,
        "deconflicted_to_pass":0,
        "events":[],
    }
    _state={
        "turns":0,
        "selected_day":None,
        "selected_mode":HOLD,
        "mode_days":Counter(),
        "mode_turns":Counter(),
        "day_selections":[],
        "surface_changed_turns":0,
        "throughput_changed_turns":0,
    }


def _select_for_day(obs):
    day=int(obs.get("day",0) or 0)
    if day>=PHASE_A_END_DAY:
        mode=HOLD
        state=_outer_state(obs)
    else:
        state=_outer_state(obs)
        mode=_route(state)
    _state["selected_day"]=day
    _state["selected_mode"]=mode
    _state["mode_days"][mode]+=1
    _state["day_selections"].append({
        "day":day,
        "hour":int(obs.get("hour",0) or 0),
        "mode":mode,
        "outer_state":state,
    })


def agent(obs):
    if not _state:
        reset_telemetry()

    day=int(obs.get("day",0) or 0)
    if _state["selected_day"]!=day:
        _select_for_day(obs)
    mode=_state["selected_mode"]

    changed=False
    if day>=PHASE_A_END_DAY or mode==HOLD:
        action=baseline.agent(obs)
    elif mode==ENGINE:
        action=variants._engine_call(obs)
    else:
        action=baseline.agent(obs)
        if mode==SURFACE:
            action,changed=variants._surface_first(obs,action)
            if changed:
                _state["surface_changed_turns"]+=1
        elif mode==THROUGHPUT:
            action,changed=variants._throughput_first(obs,action)
            if changed:
                _state["throughput_changed_turns"]+=1

    revised,changes=wr02.deconflict(obs,action)
    wr02._state["turns"]+=1
    if changes:
        wr02._state["events"].append({
            "day":day,
            "hour":int(obs.get("hour",0) or 0),
            "changes":changes,
        })

    _state["turns"]+=1
    _state["mode_turns"][mode]+=1
    return revised


def get_telemetry():
    return {
        "phase_a_router_v0":True,
        "phase_a_end_day":PHASE_A_END_DAY,
        "turns":_state.get("turns",0),
        "mode_days":dict(_state.get("mode_days",{})),
        "mode_turns":dict(_state.get("mode_turns",{})),
        "day_selections":list(_state.get("day_selections",[])),
        "surface_changed_turns":_state.get("surface_changed_turns",0),
        "throughput_changed_turns":_state.get("throughput_changed_turns",0),
        "wr02_duplicate_seen":wr02._state.get("duplicate_plant_commands_seen",0),
        "wr02_moved":wr02._state.get("deconflicted_to_move",0),
    }
