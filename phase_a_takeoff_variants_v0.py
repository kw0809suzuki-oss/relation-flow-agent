"""Phase A Takeoff Variants v0.

Three broad Battle patterns for crossing Phase A.
All are layered on the current Active Model (Body + WR-02).

A / surface_first:
  Before Day12, if own current surface is substantially occupied and the next
  LAND purchase is cash-feasible with a small survival reserve, allow one
  additional BUY_LAND. Crop choice / planting remains native.

B / throughput_first:
  Before Day12, grow working capacity toward 6 total units when cash permits.
  No crop or position is prescribed.

C / engine_first:
  Before Day12, keep native crop mix and scoring but enlarge the native
  productive target toward 85% of current unlocked capacity and lower only the
  fixed strategy reserve_base to 250. Native code still chooses crop, seed,
  land, hire, position, and quantities.

WR-02 is applied after each variant action.
D14 closure remains unchanged.
"""
import copy

import strong_origin
import strong_origin_v2_body_only_v0 as baseline
import wr02_same_tile_plant_deconfliction_v0 as wr02

PHASE_A_END_DAY=12
SURVIVAL_RESERVE=250
SURFACE_OCCUPANCY_GATE=0.55
THROUGHPUT_TARGET_UNITS=6
ENGINE_TARGET_OCCUPANCY=0.85

_mode="surface_first"
_state={}


def set_mode(mode):
    global _mode
    if mode not in ("surface_first","throughput_first","engine_first"):
        raise ValueError(mode)
    _mode=mode


def _productive_tiles(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    n=0; unlocked=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if t!="LOCKED":
                unlocked+=1
            if isinstance(t,dict) and (t.get("kind")=="PLANT" or t.get("animal")):
                n+=1
    return n,unlocked


def _land_cost(obs):
    p=int(obs["player"])
    q=len(obs["farms"][p].get("unlocked_quadrants",[]) or [])
    return {1:1000,2:2000,3:4000}.get(q)


def _insert_after_sells(market,order):
    out=[]; inserted=False
    for x in market:
        if not inserted and isinstance(x,(list,tuple)) and x and x[0]!="SELL":
            out.append(order);inserted=True
        out.append(x)
    if not inserted:
        out.append(order)
    return out[:10]


def _surface_first(obs,action):
    day=int(obs.get("day",0) or 0)
    if day>=PHASE_A_END_DAY or not isinstance(action,dict):
        return action,False
    productive,unlocked=_productive_tiles(obs)
    occupancy=productive/max(1,unlocked)
    cost=_land_cost(obs)
    p=int(obs["player"]);cash=float(obs["farms"][p].get("money",0) or 0)
    market=list(action.get("market",[]) or [])
    if (cost is None or occupancy<SURFACE_OCCUPANCY_GATE or
        cash-cost<SURVIVAL_RESERVE or
        any(isinstance(x,(list,tuple)) and x and x[0]=="BUY_LAND" for x in market)):
        return action,False
    revised=copy.deepcopy(action)
    revised["market"]=_insert_after_sells(market,["BUY_LAND"])
    return revised,True


def _throughput_first(obs,action):
    day=int(obs.get("day",0) or 0)
    if day>=PHASE_A_END_DAY or not isinstance(action,dict):
        return action,False
    p=int(obs["player"]);farm=obs["farms"][p]
    units=1+len(farm.get("hands",[]) or [])
    cash=float(farm.get("money",0) or 0)
    hires_today=int(farm.get("hires_today",0) or 0)
    cost=strong_origin.fib_hire_cost(hires_today)
    market=list(action.get("market",[]) or [])
    if (units>=THROUGHPUT_TARGET_UNITS or cash-cost<SURVIVAL_RESERVE or
        any(isinstance(x,(list,tuple)) and x and x[0]=="HIRE" for x in market)):
        return action,False
    revised=copy.deepcopy(action)
    revised["market"]=_insert_after_sells(market,["HIRE"])
    return revised,True


def _engine_call(obs):
    original_targets=strong_origin.origin_targets
    original_reserves={k:v.get("reserve_base") for k,v in strong_origin.STRATEGIES.items()}

    def expanded_targets(name,day,capacity):
        native=original_targets(name,day,capacity)
        if int(day)>=PHASE_A_END_DAY:
            return native
        current=sum(native.values())
        desired=max(current,int(capacity*ENGINE_TARGET_OCCUPANCY))
        if current<=0 or desired<=current:
            return native
        scaled={}
        assigned=0
        items=list(native.items())
        for i,(crop,n) in enumerate(items):
            if i==len(items)-1:
                scaled[crop]=max(0,desired-assigned)
            else:
                v=int(round(desired*(n/current)))
                scaled[crop]=max(0,v);assigned+=scaled[crop]
        return scaled

    try:
        strong_origin.origin_targets=expanded_targets
        if int(obs.get("day",0) or 0)<PHASE_A_END_DAY:
            for cfg in strong_origin.STRATEGIES.values():
                if "reserve_base" in cfg:
                    cfg["reserve_base"]=SURVIVAL_RESERVE
        return baseline.agent(obs)
    finally:
        strong_origin.origin_targets=original_targets
        for k,v in original_reserves.items():
            strong_origin.STRATEGIES[k]["reserve_base"]=v


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
    _state={"turns":0,"changed_turns":0,"mode":_mode,"events":[]}


def agent(obs):
    if not _state:
        reset_telemetry()

    if _mode=="engine_first":
        action=_engine_call(obs)
        changed=False
    else:
        action=baseline.agent(obs)
        if _mode=="surface_first":
            action,changed=_surface_first(obs,action)
        else:
            action,changed=_throughput_first(obs,action)

    revised,wr02_changes=wr02.deconflict(obs,action)
    wr02._state["turns"]+=1
    if wr02_changes:
        wr02._state["events"].append({
            "day":int(obs.get("day",0) or 0),
            "hour":int(obs.get("hour",0) or 0),
            "changes":wr02_changes,
        })

    _state["turns"]+=1
    if changed:
        _state["changed_turns"]+=1
        _state["events"].append({
            "day":int(obs.get("day",0) or 0),
            "hour":int(obs.get("hour",0) or 0),
            "mode":_mode,
        })
    return revised


def get_telemetry():
    return {
        "phase_a_takeoff_variant":_mode,
        "turns":_state.get("turns",0),
        "changed_turns":_state.get("changed_turns",0),
        "wr02_duplicate_seen":wr02._state.get("duplicate_plant_commands_seen",0),
        "wr02_moved":wr02._state.get("deconflicted_to_move",0),
        "body":baseline.get_telemetry(),
    }
