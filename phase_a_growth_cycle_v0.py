"""Phase A Growth Cycle v0.

Broad outer-State growth cycle layered on the current Active Model (WR-02).

Instead of selecting one global direction, Phase A composes the three already
tested broad growth directions as a cycle:

    ENGINE -> THROUGHPUT -> SURFACE -> ENGINE ...

Transitions are based only on observable World transformation:
- ENGINE -> THROUGHPUT when current productive occupancy reaches 0.70.
- THROUGHPUT -> SURFACE when total workers reaches the existing tested
  Throughput target (6).
- SURFACE -> ENGINE when unlocked quadrant count increases.

Each stage reuses the already-tested Phase A takeoff pattern implementation.
No crop, animal, tile, or market product is newly prescribed here.
WR-02 is always applied last. Day12 ends this Phase A cycle; D14 closure remains.
"""
from collections import Counter

import strong_origin_v2_body_only_v0 as baseline
import wr02_same_tile_plant_deconfliction_v0 as wr02
import phase_a_takeoff_variants_v0 as variants

PHASE_A_END_DAY=12
ENGINE="engine"
THROUGHPUT="throughput"
SURFACE="surface"

_state={}


def _outer(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    productive=0;unlocked=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if t!="LOCKED": unlocked+=1
            if isinstance(t,dict) and (t.get("kind")=="PLANT" or t.get("animal")):
                productive+=1
    workers=1+len(farm.get("hands",[]) or [])
    quadrants=len(farm.get("unlocked_quadrants",[]) or [])
    return {
      "productive":productive,
      "unlocked":unlocked,
      "occupancy":productive/max(1,unlocked),
      "workers":workers,
      "quadrants":quadrants,
      "cash":float(farm.get("money",0) or 0),
    }


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
      "stage":ENGINE,
      "stage_entry":None,
      "stage_turns":Counter(),
      "transitions":[],
      "surface_changed_turns":0,
      "throughput_changed_turns":0,
    }


def _enter(stage,obs,reason):
    s=_outer(obs)
    _state["stage"]=stage
    _state["stage_entry"]=s
    _state["transitions"].append({
      "day":int(obs.get("day",0) or 0),
      "hour":int(obs.get("hour",0) or 0),
      "to":stage,
      "reason":reason,
      "outer_state":s,
    })


def _advance(obs):
    s=_outer(obs)
    stage=_state["stage"]
    entry=_state.get("stage_entry") or s

    if stage==ENGINE and s["occupancy"]>=0.70:
        _enter(THROUGHPUT,obs,"productive_occupancy_reached")
    elif stage==THROUGHPUT and s["workers"]>=variants.THROUGHPUT_TARGET_UNITS:
        _enter(SURFACE,obs,"throughput_target_reached")
    elif stage==SURFACE and s["quadrants"]>entry["quadrants"]:
        _enter(ENGINE,obs,"new_surface_realized")


def agent(obs):
    if not _state:
        reset_telemetry()
    day=int(obs.get("day",0) or 0)

    if _state["stage_entry"] is None:
        _state["stage_entry"]=_outer(obs)

    if day<PHASE_A_END_DAY:
        _advance(obs)
        stage=_state["stage"]
    else:
        stage="hold"

    changed=False
    if stage=="hold":
        action=baseline.agent(obs)
    elif stage==ENGINE:
        action=variants._engine_call(obs)
    else:
        action=baseline.agent(obs)
        if stage==THROUGHPUT:
            action,changed=variants._throughput_first(obs,action)
            if changed:_state["throughput_changed_turns"]+=1
        elif stage==SURFACE:
            action,changed=variants._surface_first(obs,action)
            if changed:_state["surface_changed_turns"]+=1

    revised,changes=wr02.deconflict(obs,action)
    wr02._state["turns"]+=1
    if changes:
        wr02._state["events"].append({
          "day":day,"hour":int(obs.get("hour",0) or 0),"changes":changes
        })

    _state["turns"]+=1
    _state["stage_turns"][stage]+=1
    return revised


def get_telemetry():
    return {
      "phase_a_growth_cycle_v0":True,
      "phase_a_end_day":PHASE_A_END_DAY,
      "stage_turns":dict(_state.get("stage_turns",{})),
      "transitions":list(_state.get("transitions",[])),
      "throughput_changed_turns":_state.get("throughput_changed_turns",0),
      "surface_changed_turns":_state.get("surface_changed_turns",0),
      "wr02_duplicate_seen":wr02._state.get("duplicate_plant_commands_seen",0),
      "wr02_moved":wr02._state.get("deconflicted_to_move",0),
    }
