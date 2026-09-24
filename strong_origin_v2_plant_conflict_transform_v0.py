"""Strong Origin v2 Day4 PLANT Conflict Transform v0.

Transformation-only candidate.

The Body's projected action is generated unchanged by Body-only v0.
Only on Day4, when >=2 already-projected PLANT requests are issued by units
currently standing on the same empty tile, the transformation adapter changes
which existing request is allowed to reach the public interpreter:

- baseline world execution effectively gives the lowest unit index first use
  of the empty tile;
- candidate gives the highest unit index among the already-projected PLANT
  requests the single transformable slot;
- all other conflicting PLANT requests on that tile become PASS.

No new action, target tile, crop preference, reachable-future reasoning,
evaluation or direction is added.
"""
import copy
from collections import Counter

import strong_origin_v2_body_only_v0 as body_only

_state={}
_last_trace={}


def reset_telemetry():
    global _state,_last_trace
    body_only.reset_telemetry()
    _state={
        "turns":0,
        "modified_turns":0,
        "conflict_groups":0,
        "projected_conflict_requests":0,
        "suppressed_requests":0,
        "winner_crop_counts":Counter(),
        "events":[],
    }
    _last_trace={}


def _unit_positions(me):
    return [tuple(me["farmer"])] + [tuple(x) for x in (me.get("hands",[]) or [])]


def _unit_actions(action,n_units):
    out=[copy.deepcopy(action.get("farmer",["PASS"]))]
    out.extend(copy.deepcopy(action.get("hands",[]) or []))
    while len(out)<n_units:
        out.append(["PASS"])
    return out[:n_units]


def _action_dict(actions):
    return {
        "farmer":copy.deepcopy(actions[0] if actions else ["PASS"]),
        "hands":copy.deepcopy(actions[1:]),
    }


def _resolve_day4_plant_conflicts(obs,projected):
    if int(obs.get("day",-1))!=4 or not isinstance(projected,dict):
        return copy.deepcopy(projected),[]

    player=int(obs["player"])
    me=obs["farms"][player]
    private=obs.get("private",{}) or {}
    seeds=private.get("seeds",{}) or {}
    positions=_unit_positions(me)
    actions=_unit_actions(projected,len(positions))

    groups={}
    for idx,(pos,act) in enumerate(zip(positions,actions)):
        if not (isinstance(act,list) and len(act)>=2 and act[0]=="PLANT"):
            continue
        x,y=pos
        try: tile=me["tiles"][y][x]
        except Exception: continue
        if tile is not None:
            continue
        crop=str(act[1])
        if int(seeds.get(crop,0) or 0)<=0:
            continue
        groups.setdefault(pos,[]).append(idx)

    effective=copy.deepcopy(actions)
    events=[]
    for pos,indices in sorted(groups.items()):
        if len(indices)<2:
            continue
        winner=max(indices)  # generic unit-order flip; crop name is not consulted
        for idx in indices:
            if idx!=winner:
                effective[idx]=["PASS"]
        events.append({
            "tile":list(pos),
            "projected_unit_indices":list(indices),
            "projected_actions":[copy.deepcopy(actions[i]) for i in indices],
            "transformable_opportunities":1,
            "winner_unit_index":winner,
            "winner_action":copy.deepcopy(actions[winner]),
            "suppressed_unit_indices":[i for i in indices if i!=winner],
            "rule":"highest_unit_index_existing_request_wins",
        })

    out=_action_dict(effective)
    # market is never part of this transform.
    out["market"]=copy.deepcopy(projected.get("market",[]) or [])
    return out,events


def agent(obs):
    global _state,_last_trace
    if not _state:
        reset_telemetry()

    projected=body_only.agent(obs)
    effective,events=_resolve_day4_plant_conflicts(obs,projected)

    _state["turns"]+=1
    if events:
        _state["modified_turns"]+=1
        _state["conflict_groups"]+=len(events)
        for e in events:
            _state["projected_conflict_requests"]+=len(e["projected_unit_indices"])
            _state["suppressed_requests"]+=len(e["suppressed_unit_indices"])
            a=e["winner_action"]
            crop=str(a[1]) if isinstance(a,list) and len(a)>=2 else "UNKNOWN"
            _state["winner_crop_counts"][crop]+=1
        _state["events"].append({
            "day":int(obs.get("day",-1)),
            "hour":int(obs.get("hour",-1)),
            "events":copy.deepcopy(events),
        })

    _last_trace={
        "day":int(obs.get("day",-1)),
        "hour":int(obs.get("hour",-1)),
        "projected_action":copy.deepcopy(projected),
        "effective_action":copy.deepcopy(effective),
        "modified":bool(events),
        "conflicts":copy.deepcopy(events),
    }
    return effective


def get_last_trace():
    return copy.deepcopy(_last_trace)


def get_telemetry():
    out=dict(body_only.get_telemetry())
    out.update({
        "plant_conflict_transform_v0":True,
        "transform_rule":"day4_same_empty_tile_highest_unit_index_existing_request_wins",
        "transform_turns":_state.get("turns",0),
        "modified_turns":_state.get("modified_turns",0),
        "conflict_groups":_state.get("conflict_groups",0),
        "projected_conflict_requests":_state.get("projected_conflict_requests",0),
        "suppressed_requests":_state.get("suppressed_requests",0),
        "winner_crop_counts":dict(_state.get("winner_crop_counts",{})),
        "transform_events":copy.deepcopy(_state.get("events",[])),
    })
    return out
