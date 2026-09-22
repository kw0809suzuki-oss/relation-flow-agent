"""Final-mile Liquidation Candidate v0.

Baseline:
- Current Combat Model with adopted D14 expansion closure.
- HIRE preserved.
- Native HARVEST and SELL behavior unchanged.

Candidate:
- On final day (day 29), if a unit carries sellable crop inventory
  (WHEAT / STRAWBERRY / MELON), prioritize returning to a shed-adjacent cell.
- If already shed-adjacent, DROP immediately.
- Native SELL then handles shed stock on subsequent turns.

No harvest override, no price prediction, no earlier closure, no rescue condition.
"""

import copy
import whole_flow_control_agent as native

FINAL_DAY = 29
SELLABLE_CROPS = ("WHEAT", "STRAWBERRY", "MELON")
_state = {}

def reset_experiment():
    global _state
    _state = {
        "eligible": 0,
        "move_overrides": 0,
        "drop_overrides": 0,
        "events": [],
    }
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def _shed_cells(board_size):
    h = board_size // 2
    return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]

def _adjacent_shed(pos, board_size):
    return tuple(pos) in set(_shed_cells(board_size))

def _nearest(src, points):
    x,y=src
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

    actions=native.agent(obs)
    if not isinstance(actions,dict):
        return actions

    day=int(obs.get("day",0) or 0)
    if day != FINAL_DAY:
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
        inv=inventories[idx] if idx<len(inventories) else {}
        qty=_crop_count(inv)
        if qty<=0:
            continue

        _state["eligible"] += 1
        before=farmer_action if idx==0 else hand_actions[idx-1]
        if _adjacent_shed(pos,board_size):
            after=["DROP"]
            _state["drop_overrides"] += 1
            kind="drop"
        else:
            target=_nearest(tuple(pos),shed_cells)
            after=_move(tuple(pos),target)
            _state["move_overrides"] += 1
            kind="return"

        if idx==0:
            farmer_action=after
        else:
            hand_actions[idx-1]=after

        changes.append({
            "unit_index":idx,
            "position":list(pos),
            "crop_count":qty,
            "before":copy.deepcopy(before),
            "after":copy.deepcopy(after),
            "kind":kind,
        })

    revised["farmer"]=farmer_action
    revised["hands"]=hand_actions

    if changes:
        _state["events"].append({
            "day":day,
            "money":me.get("money"),
            "changes":changes,
        })

    return revised

def get_experiment_telemetry():
    return copy.deepcopy(_state)

def get_trace():
    return native.get_trace()
