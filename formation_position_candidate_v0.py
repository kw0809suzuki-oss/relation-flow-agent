"""Formation Position Candidate v0.

Single intervention:
- Day0 h12 only
- move up to three units onto distinct adjacent empty unlocked tiles
- do not change market orders
- do not force crop/animal choice
- from h13 onward, return completely to Body-only native behavior
"""
import copy
import strong_origin_v2_body_only_v0 as baseline

_state={}

DIRS=(
    ("NORTH",0,-1),
    ("EAST",1,0),
    ("SOUTH",0,1),
    ("WEST",-1,0),
)

def reset_telemetry():
    global _state
    baseline.reset_telemetry()
    _state={
        "modified_turns":0,
        "modified_unit_actions":0,
        "targets":[],
    }

def get_telemetry():
    out=dict(baseline.get_telemetry())
    out.update(_state)
    out["formation_position_candidate_v0"]=True
    return out

def _positions(me):
    out=[("farmer",0,tuple(me.get("farmer",())))]
    for i,p in enumerate(me.get("hands",[]) or []):
        out.append(("hand",i,tuple(p)))
    return out

def _is_empty(tiles,x,y):
    return 0<=y<len(tiles) and 0<=x<len(tiles[y]) and tiles[y][x] is None

def agent(obs):
    global _state
    if not _state:
        reset_telemetry()

    action=baseline.agent(obs)
    if int(obs.get("day",0) or 0)!=0 or int(obs.get("hour",0) or 0)!=12:
        return action
    if not isinstance(action,dict):
        return action

    p=int(obs["player"])
    me=obs["farms"][p]
    tiles=me.get("tiles",[]) or []
    revised=copy.deepcopy(action)
    hands=list(revised.get("hands",[]) or [])
    reserved=set()
    modified=[]

    for kind,idx,pos in _positions(me):
        if len(modified)>=3 or len(pos)<2:
            continue
        x,y=int(pos[0]),int(pos[1])

        chosen=None
        for opname,dx,dy in DIRS:
            tx,ty=x+dx,y+dy
            if (tx,ty) in reserved:
                continue
            if _is_empty(tiles,tx,ty):
                chosen=(opname,tx,ty)
                break
        if chosen is None:
            continue

        opname,tx,ty=chosen
        if kind=="farmer":
            revised["farmer"]=[opname]
        else:
            while len(hands)<=idx:
                hands.append(["PASS"])
            hands[idx]=[opname]
        reserved.add((tx,ty))
        modified.append({
            "unit_kind":kind,
            "unit_index":idx,
            "from":[x,y],
            "to":[tx,ty],
            "action":[opname],
        })

    if modified:
        revised["hands"]=hands
        _state["modified_turns"]+=1
        _state["modified_unit_actions"]+=len(modified)
        _state["targets"].extend(modified)
    return revised
