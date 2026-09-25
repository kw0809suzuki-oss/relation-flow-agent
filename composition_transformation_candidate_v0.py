"""Composition Transformation Candidate v0.

Single intervention:
- Day0 h14 only
- replace exactly one native PLANT WHEAT action with PLANT MELON
- only when MELON seed stock is actually present
- preserve unit, tile, timing, action count, movement, and market orders
- all later behavior remains native Body-only
"""
import copy
import strong_origin_v2_body_only_v0 as baseline

_state={}

def reset_telemetry():
    global _state
    baseline.reset_telemetry()
    _state={
        "modified_turns":0,
        "replaced_actions":0,
        "replacement":None,
    }

def get_telemetry():
    out=dict(baseline.get_telemetry())
    out.update(_state)
    out["composition_transformation_candidate_v0"]=True
    return out

def _is_wheat_plant(a):
    return isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="PLANT" and a[1]=="WHEAT"

def agent(obs):
    global _state
    if not _state:
        reset_telemetry()

    action=baseline.agent(obs)
    if int(obs.get("day",0) or 0)!=0 or int(obs.get("hour",0) or 0)!=14:
        return action
    if not isinstance(action,dict):
        return action

    private=obs.get("private",{}) or {}
    melon=int((private.get("seeds",{}) or {}).get("MELON",0) or 0)
    if melon<=0:
        return action

    revised=copy.deepcopy(action)

    if _is_wheat_plant(revised.get("farmer")):
        revised["farmer"]=["PLANT","MELON"]
        _state["modified_turns"]+=1
        _state["replaced_actions"]+=1
        _state["replacement"]={"unit_kind":"farmer","unit_index":0,"from":["PLANT","WHEAT"],"to":["PLANT","MELON"]}
        return revised

    hands=list(revised.get("hands",[]) or [])
    for i,a in enumerate(hands):
        if _is_wheat_plant(a):
            hands[i]=["PLANT","MELON"]
            revised["hands"]=hands
            _state["modified_turns"]+=1
            _state["replaced_actions"]+=1
            _state["replacement"]={"unit_kind":"hand","unit_index":i,"from":["PLANT","WHEAT"],"to":["PLANT","MELON"]}
            return revised

    return action
