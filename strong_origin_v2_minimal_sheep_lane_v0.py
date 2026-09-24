"""Strong Origin v2 Minimal SHEEP Lane Probe v0.

Body-only v0 runs first and remains the authority for crop/COW/LAND/HIRE logic.
This file adds one narrow external overlay for a single early SHEEP lane:

1. append at most one SHEEP purchase after the native market orders, only after
   the native two-COW entrance is projected and enough Cash remains;
2. use at most one existing unit at a time for SHEEP pickup/place/feed/harvest
   and returning WOOL to the shed.

No native COW target, crop target, market order, LAND/HIRE rule or D14 closure
is replaced. The SHEEP order is appended, never inserted ahead of baseline
orders, so it cannot pre-empt an earlier native market order.
"""
import copy

import strong_origin_v2_body_only_v0 as body_only

SHEEP_COST=500
POST_SHEEP_CASH_FLOOR=700
ENTRY_END_DAY=4


def _fib(n):
    a,b=1,1
    for _ in range(n):
        a,b=b,a+b
    return a


def _adjacent_shed(x,y,board_size):
    h=board_size//2
    return (x,y) in {(h-1,h-1),(h,h-1),(h-1,h),(h,h)}


def _shed_access(board_size):
    h=board_size//2
    return [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]


def _nearest(src,points):
    if not points:return None
    x,y=src
    return min(points,key=lambda p:abs(p[0]-x)+abs(p[1]-y))


def _move(src,dst):
    x,y=src;tx,ty=dst
    if x<tx:return ["EAST"]
    if x>tx:return ["WEST"]
    if y<ty:return ["SOUTH"]
    if y>ty:return ["NORTH"]
    return ["PASS"]


def _animal_total(obs,animal):
    private=obs.get("private",{}) or {}
    p=int(obs["player"])
    farm=obs["farms"][p]
    n=int((private.get("shed",{}) or {}).get(animal,0) or 0)
    for inv in private.get("inventories",[]) or []:
        n+=int((inv or {}).get(animal,0) or 0)
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if isinstance(t,dict) and t.get("animal")==animal:
                n+=1
    return n


def _project_native_spend(obs,market):
    p=int(obs["player"])
    me=obs["farms"][p]
    prices=(obs.get("market",{}) or {}).get("prices",{}) or {}
    seed_cost={"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
    animal_cost={"GOOSE":300,"COW":400,"SHEEP":500}
    projected=0.0
    hires=int(me.get("hires_today",0) or 0)
    quadrants=len(me.get("unlocked_quadrants",[]) or [])
    for o in market:
        if not isinstance(o,(list,tuple)) or not o: continue
        op=o[0]
        if op=="HIRE":
            projected+=_fib(hires);hires+=1
        elif op=="BUY_LAND":
            projected+={1:1000,2:2000,3:4000}.get(quadrants,10**9);quadrants+=1
        elif op=="BUY_SEED" and len(o)>=3:
            projected+=seed_cost.get(o[1],10**9)*int(o[2])
        elif op=="BUY_ANIMAL" and len(o)>=3:
            projected+=animal_cost.get(o[1],10**9)*int(o[2])
        elif op=="BUY_PRODUCT" and len(o)>=3:
            projected+=float(prices.get(o[1],0) or 0)*int(o[2])
    return projected


def _append_sheep_purchase(obs,action):
    if not isinstance(action,dict): return action
    day=int(obs.get("day",0) or 0)
    if day>ENTRY_END_DAY or _animal_total(obs,"SHEEP")>0:
        return action

    market=list(action.get("market",[]) or [])
    if len(market)>=10:
        return action

    cows=_animal_total(obs,"COW")
    ordered_cows=sum(
        int(o[2]) for o in market
        if isinstance(o,(list,tuple)) and len(o)>=3 and o[0]=="BUY_ANIMAL" and o[1]=="COW"
    )
    if cows+ordered_cows<2:
        return action

    p=int(obs["player"])
    cash=float(obs["farms"][p].get("money",0) or 0)
    native_spend=_project_native_spend(obs,market)
    if cash-native_spend-SHEEP_COST<POST_SHEEP_CASH_FLOOR:
        return action

    revised=copy.deepcopy(action)
    revised["market"]=market+[["BUY_ANIMAL","SHEEP",1]]
    return revised


def _unit_context(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    private=obs.get("private",{}) or {}
    positions=[tuple(me.get("farmer",[0,0]))]+[tuple(x) for x in me.get("hands",[]) or []]
    invs=list(private.get("inventories",[]) or [])
    while len(invs)<len(positions):invs.append({})
    return me,private,positions,invs


def _set_unit(action,idx,new_action,unit_count):
    revised=copy.deepcopy(action)
    if idx==0:
        revised["farmer"]=new_action
    else:
        hands=list(revised.get("hands",[]) or [])
        while len(hands)<unit_count-1:hands.append(["PASS"])
        hands[idx-1]=new_action
        revised["hands"]=hands
    return revised


def _sheep_overlay(obs,action):
    if not isinstance(action,dict):return action
    me,private,positions,invs=_unit_context(obs)
    tiles=me.get("tiles",[]) or []
    board_size=len(tiles)
    shed=private.get("shed",{}) or {}

    # Return harvested WOOL first; native market logic will sell it from shed.
    wool_carriers=[
        (idx,pos) for idx,(pos,inv) in enumerate(zip(positions,invs))
        if int((inv or {}).get("WOOL",0) or 0)>0
    ]
    if wool_carriers:
        idx,pos=min(wool_carriers,key=lambda z:min(abs(z[1][0]-q[0])+abs(z[1][1]-q[1]) for q in _shed_access(board_size)))
        if _adjacent_shed(pos[0],pos[1],board_size):
            return _set_unit(action,idx,["DROP"],len(positions))
        return _set_unit(action,idx,_move(pos,_nearest(pos,_shed_access(board_size))),len(positions))

    # If the bought SHEEP is still in the shed, get one unit to pick it up.
    sheep_carriers=[
        (idx,pos) for idx,(pos,inv) in enumerate(zip(positions,invs))
        if int((inv or {}).get("SHEEP",0) or 0)>0
    ]
    if not sheep_carriers and int(shed.get("SHEEP",0) or 0)>0:
        scored=[(min(abs(pos[0]-q[0])+abs(pos[1]-q[1]) for q in _shed_access(board_size)),idx,pos) for idx,pos in enumerate(positions)]
        _,idx,pos=min(scored)
        if _adjacent_shed(pos[0],pos[1],board_size):
            return _set_unit(action,idx,["PICKUP","SHEEP",1],len(positions))
        return _set_unit(action,idx,_move(pos,_nearest(pos,_shed_access(board_size))),len(positions))

    # Carrying SHEEP: build/place the pasture with only the carrier.
    if sheep_carriers:
        idx,pos=sheep_carriers[0]
        x,y=pos
        tile=tiles[y][x]
        if isinstance(tile,dict) and tile.get("kind")=="PASTURE" and not tile.get("animal"):
            return _set_unit(action,idx,["PLACE","SHEEP",1],len(positions))
        empty_pastures=[]
        empty_tiles=[]
        for yy,row in enumerate(tiles):
            for xx,t in enumerate(row):
                if isinstance(t,dict) and t.get("kind")=="PASTURE" and not t.get("animal"):
                    empty_pastures.append((xx,yy))
                elif t is None:
                    empty_tiles.append((xx,yy))
        target=_nearest(pos,empty_pastures)
        if target is not None:
            return _set_unit(action,idx,_move(pos,target),len(positions))
        if tile is None:
            return _set_unit(action,idx,["BUILD_PASTURE"],len(positions))
        target=_nearest(pos,empty_tiles)
        if target is not None:
            return _set_unit(action,idx,_move(pos,target),len(positions))
        return action

    sheep_tiles=[]
    for y,row in enumerate(tiles):
        for x,t in enumerate(row):
            if isinstance(t,dict) and t.get("animal")=="SHEEP":
                sheep_tiles.append((x,y,t))
    if not sheep_tiles:
        return action

    sx,sy,sheep=sheep_tiles[0]
    target=(sx,sy)

    # Survival first: one feed per day.
    if not sheep.get("fed_today",False):
        wheat_units=[
            (abs(pos[0]-sx)+abs(pos[1]-sy),idx,pos)
            for idx,(pos,inv) in enumerate(zip(positions,invs))
            if int((inv or {}).get("WHEAT",0) or 0)>0
        ]
        if wheat_units:
            _,idx,pos=min(wheat_units)
            if pos==target:
                return _set_unit(action,idx,["FEED"],len(positions))
            return _set_unit(action,idx,_move(pos,target),len(positions))

        if int(shed.get("WHEAT",0) or 0)>0:
            scored=[(min(abs(pos[0]-q[0])+abs(pos[1]-q[1]) for q in _shed_access(board_size)),idx,pos) for idx,pos in enumerate(positions)]
            _,idx,pos=min(scored)
            if _adjacent_shed(pos[0],pos[1],board_size):
                return _set_unit(action,idx,["PICKUP","WHEAT",min(3,int(shed.get("WHEAT",0) or 0))],len(positions))
            return _set_unit(action,idx,_move(pos,_nearest(pos,_shed_access(board_size))),len(positions))

    # Once fed, collect actual WOOL when it exists.
    if int(sheep.get("yield_units",0) or 0)>0:
        scored=[(abs(pos[0]-sx)+abs(pos[1]-sy),idx,pos) for idx,pos in enumerate(positions)]
        _,idx,pos=min(scored)
        if pos==target:
            return _set_unit(action,idx,["HARVEST"],len(positions))
        return _set_unit(action,idx,_move(pos,target),len(positions))

    return action


def agent(obs):
    action=body_only.agent(obs)
    action=_append_sheep_purchase(obs,action)
    action=_sheep_overlay(obs,action)
    return action


def reset_telemetry():
    return body_only.reset_telemetry()


def get_telemetry():
    out=dict(body_only.get_telemetry())
    out["minimal_sheep_lane_probe_v0"]=True
    out["baseline_body_first"]=True
    return out
