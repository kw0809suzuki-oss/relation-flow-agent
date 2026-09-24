"""Strong Origin v2 Minimal SHEEP Lane Probe v0.

Baseline Body-only is unchanged. During candidate.agent only, Strong Origin
Body's livestock overlay is swapped from frozen G8 to the minimal SHEEP probe.

Direct intended difference:
- preserve native COW target;
- once the two-COW entrance is reachable, buy at most one SHEEP through Day4;
- reuse generic pasture/harvest/fertilizer/drop mechanics;
- reserve one unit only when necessary to keep the probe SHEEP fed/alive.

No crop target, LAND, HIRE, D14 closure, or post-Day4 strategy rule is added.
"""
import copy

import strong_origin_body as body
import strong_origin_v2_body_only_v0 as body_only
import g8_minimal_sheep_lane_v0 as sheep_livestock


def _call(fn,*args,**kwargs):
    old=body.livestock
    body.livestock=sheep_livestock
    try:
        return fn(*args,**kwargs)
    finally:
        body.livestock=old


def _adjacent_shed(x,y,board_size):
    h=board_size//2
    return (x,y) in {(h-1,h-1),(h,h-1),(h-1,h),(h,h)}


def _shed_access(board_size):
    h=board_size//2
    return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]


def _move(src,dst):
    x,y=src;tx,ty=dst
    if x<tx:return ["EAST"]
    if x>tx:return ["WEST"]
    if y<ty:return ["SOUTH"]
    if y>ty:return ["NORTH"]
    return ["PASS"]


def _nearest(src,points):
    if not points:return None
    x,y=src
    return min(points,key=lambda p:abs(p[0]-x)+abs(p[1]-y))


def _apply_sheep_feed_lane(obs,action):
    if not isinstance(action,dict):
        return action

    p=int(obs["player"])
    me=obs["farms"][p]
    private=obs.get("private",{}) or {}
    tiles=me.get("tiles",[]) or []
    board_size=len(tiles)

    sheep=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            if isinstance(t,dict) and t.get("animal")=="SHEEP":
                sheep.append((x,y,t))
    if not sheep:
        return action

    # The lane exists only to make the experimental SHEEP a viable productive
    # asset. Once it is fed today, native Body-only behavior is left untouched.
    unfed=[(x,y,t) for x,y,t in sheep if not t.get("fed_today",False)]
    if not unfed:
        return action

    target=(unfed[0][0],unfed[0][1])
    positions=[tuple(me.get("farmer",[0,0]))]+[tuple(x) for x in me.get("hands",[]) or []]
    inventories=list(private.get("inventories",[]) or [])
    while len(inventories)<len(positions):
        inventories.append({})

    def set_unit(idx,new_action):
        revised=copy.deepcopy(action)
        if idx==0:
            revised["farmer"]=new_action
        else:
            hands=list(revised.get("hands",[]) or [])
            while len(hands)<len(positions)-1:
                hands.append(["PASS"])
            hands[idx-1]=new_action
            revised["hands"]=hands
        return revised

    # First use a unit already carrying feed.
    candidates=[
        (abs(pos[0]-target[0])+abs(pos[1]-target[1]),idx,pos)
        for idx,(pos,inv) in enumerate(zip(positions,inventories))
        if int((inv or {}).get("WHEAT",0) or 0)>0
    ]
    if candidates:
        _,idx,pos=min(candidates)
        if pos==target:
            return set_unit(idx,["FEED"])
        return set_unit(idx,_move(pos,target))

    # Otherwise route one nearest unit to the shed and pick up feed.
    shed_wheat=int((private.get("shed",{}) or {}).get("WHEAT",0) or 0)
    if shed_wheat<=0:
        return action

    scored=[]
    access=_shed_access(board_size)
    for idx,pos in enumerate(positions):
        dst=_nearest(pos,access)
        dist=abs(pos[0]-dst[0])+abs(pos[1]-dst[1])
        scored.append((dist,idx,pos,dst))
    _,idx,pos,dst=min(scored)

    if _adjacent_shed(pos[0],pos[1],board_size):
        return set_unit(idx,["PICKUP","WHEAT",min(3,shed_wheat)])
    return set_unit(idx,_move(pos,dst))


def agent(obs):
    action=_call(body_only.agent,obs)
    return _apply_sheep_feed_lane(obs,action)


def reset_telemetry():
    return _call(body_only.reset_telemetry)


def get_telemetry():
    out=dict(body_only.get_telemetry())
    out["minimal_sheep_lane_probe_v0"]=True
    out["sheep_feed_lane_reserved_when_unfed"]=True
    return out
