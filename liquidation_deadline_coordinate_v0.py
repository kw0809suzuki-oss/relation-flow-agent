"""Liquidation Deadline Coordinate v0.

Strategic coordinate:
- Phase: Liquidation only when a carried crop is at risk of missing terminal cash conversion.
- Objective: convert already-created value into cash before the season ends.
- Constraint: do not alter native HARVEST, BUY, HIRE, or SELL logic.

Experimental clock:
- 24 agent calls per day, 30 days -> 720 calls total.
- This is treated as an experiment clock hypothesis consistent with observed traces,
  not as a promoted game-rule claim.

For each unit carrying WHEAT/STRAWBERRY/MELON:
  required_turns = Manhattan distance to nearest shed-adjacent cell + DROP + SELL
If required_turns >= remaining_turns:
  route to shed, or DROP if already adjacent.
"""

import copy
import whole_flow_control_agent as native

SELLABLE_CROPS=("WHEAT","STRAWBERRY","MELON")
TURNS_PER_DAY=24
SEASON_DAYS=30
TOTAL_TURNS=TURNS_PER_DAY*SEASON_DAYS

_state={}

def reset_experiment():
    global _state
    _state={
        "call_index":0,
        "eligible":0,
        "deadline_hits":0,
        "move_overrides":0,
        "drop_overrides":0,
        "events":[],
    }
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def _shed_cells(board_size):
    h=board_size//2
    return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]

def _nearest_distance(pos, points):
    x,y=pos
    return min(abs(px-x)+abs(py-y) for px,py in points)

def _nearest(pos, points):
    x,y=pos
    return min(points,key=lambda p:abs(p[0]-x)+abs(p[1]-y))

def _move(src,dst):
    x,y=src; tx,ty=dst
    if x<tx:return ["EAST"]
    if x>tx:return ["WEST"]
    if y<ty:return ["SOUTH"]
    if y>ty:return ["NORTH"]
    return ["PASS"]

def _crop_count(inv):
    if not isinstance(inv,dict):
        return 0
    return sum(int(inv.get(k,0) or 0) for k in SELLABLE_CROPS)

def agent(obs):
    if not _state:
        reset_experiment()

    call_index=_state["call_index"]
    _state["call_index"] += 1
    remaining_turns=max(0,TOTAL_TURNS-call_index)

    actions=native.agent(obs)
    if not isinstance(actions,dict):
        return actions

    p=int(obs["player"])
    me=obs["farms"][p]
    positions=[me.get("farmer")]+list(me.get("hands",[]) or [])
    private=obs.get("private",{}) or {}
    inventories=list(private.get("inventories",[]) or [])
    while len(inventories)<len(positions):
        inventories.append({})

    board_size=len(me.get("tiles",[]) or [])
    shed_cells=_shed_cells(board_size)

    revised=copy.deepcopy(actions)
    farmer_action=revised.get("farmer",["PASS"])
    hand_actions=list(revised.get("hands",[]) or [])
    while len(hand_actions)<max(0,len(positions)-1):
        hand_actions.append(["PASS"])

    changes=[]
    for idx,pos in enumerate(positions):
        if not isinstance(pos,(list,tuple)) or len(pos)!=2:
            continue
        qty=_crop_count(inventories[idx] if idx<len(inventories) else {})
        if qty<=0:
            continue

        _state["eligible"] += 1
        dist=_nearest_distance(tuple(pos),shed_cells)
        required_turns=dist+2  # travel + DROP + next-turn SELL
        if required_turns < remaining_turns:
            continue

        _state["deadline_hits"] += 1
        before=farmer_action if idx==0 else hand_actions[idx-1]
        if dist==0:
            after=["DROP"]
            kind="drop"
            _state["drop_overrides"] += 1
        else:
            target=_nearest(tuple(pos),shed_cells)
            after=_move(tuple(pos),target)
            kind="return"
            _state["move_overrides"] += 1

        if idx==0:
            farmer_action=after
        else:
            hand_actions[idx-1]=after

        changes.append({
            "unit_index":idx,
            "position":list(pos),
            "crop_count":qty,
            "distance_to_shed":dist,
            "required_turns":required_turns,
            "remaining_turns":remaining_turns,
            "before":copy.deepcopy(before),
            "after":copy.deepcopy(after),
            "kind":kind,
        })

    revised["farmer"]=farmer_action
    revised["hands"]=hand_actions

    if changes:
        _state["events"].append({
            "call_index":call_index,
            "day":int(obs.get("day",0) or 0),
            "remaining_turns":remaining_turns,
            "money":me.get("money"),
            "changes":changes,
        })
    return revised

def get_experiment_telemetry():
    return copy.deepcopy(_state)

def get_trace():
    return native.get_trace()
