"""WR-02: Same-tile PLANT deconfliction v0.

Observed connection gap:
multiple final PLANT commands can be projected from units standing on the same
empty tile in the same turn. Only one can transform that tile into a crop asset.

Minimal intervention:
- Day14+ only.
- Keep the first PLANT at each occupied coordinate unchanged.
- For later PLANT commands from the same coordinate, move that unit one step
  toward a distinct currently-empty unlocked tile when available; otherwise PASS.
- Do not change crop choice, market orders, quantities, or any non-duplicate
  PLANT action.
"""
import copy

import strong_origin_v2_body_only_v0 as baseline

START_DAY=14
_state={}


def reset_telemetry():
    global _state
    baseline.reset_telemetry()
    _state={
        "turns":0,
        "duplicate_plant_commands_seen":0,
        "deconflicted_to_move":0,
        "deconflicted_to_pass":0,
        "events":[],
    }


def _move(src,dst):
    x,y=src; tx,ty=dst
    if x<tx: return ["EAST"]
    if x>tx: return ["WEST"]
    if y<ty: return ["SOUTH"]
    if y>ty: return ["NORTH"]
    return ["PASS"]


def _nearest_distinct_empty(src,empty,reserved):
    x,y=src
    candidates=[p for p in empty if p!=src and p not in reserved]
    if not candidates:
        return None
    return min(candidates,key=lambda p:abs(p[0]-x)+abs(p[1]-y))


def deconflict(obs,action):
    if not isinstance(action,dict) or int(obs.get("day",0) or 0)<START_DAY:
        return action,[]

    me=obs["farms"][int(obs["player"])]
    tiles=me["tiles"]
    positions=[tuple(me["farmer"])] + [tuple(p) for p in me.get("hands",[]) or []]
    acts=[copy.deepcopy(action.get("farmer",["PASS"]))] + [
        copy.deepcopy(a) for a in (action.get("hands",[]) or [])
    ]
    while len(acts)<len(positions):
        acts.append(["PASS"])

    empty=[]
    for y,row in enumerate(tiles):
        for x,tile in enumerate(row):
            if tile is None:
                empty.append((x,y))

    first_at={}
    reserved=set()
    changes=[]
    for idx,a in enumerate(acts):
        if not (isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="PLANT"):
            continue
        if idx>=len(positions):
            continue
        pos=positions[idx]
        if pos not in first_at:
            first_at[pos]=idx
            continue

        _state["duplicate_plant_commands_seen"]+=1
        target=_nearest_distinct_empty(pos,empty,reserved)
        if target is None:
            replacement=["PASS"]
            _state["deconflicted_to_pass"]+=1
        else:
            reserved.add(target)
            replacement=_move(pos,target)
            _state["deconflicted_to_move"]+=1
        changes.append({
            "unit_index":idx,
            "position":list(pos),
            "original":copy.deepcopy(a),
            "replacement":replacement,
            "target":list(target) if target is not None else None,
        })
        acts[idx]=replacement

    if not changes:
        return action,[]

    revised=copy.deepcopy(action)
    revised["farmer"]=acts[0]
    revised["hands"]=acts[1:1+len(me.get("hands",[]) or [])]
    return revised,changes


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()
    native=baseline.agent(obs)
    revised,changes=deconflict(obs,native)
    _state["turns"]+=1
    if changes:
        _state["events"].append({
            "day":int(obs.get("day",0) or 0),
            "hour":int(obs.get("hour",0) or 0),
            "changes":changes,
        })
    return revised


def get_telemetry():
    out=dict(baseline.get_telemetry())
    out.update({
        "wr02_same_tile_plant_deconfliction":True,
        **_state,
    })
    return out
