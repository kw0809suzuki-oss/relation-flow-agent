#!/usr/bin/env python3
"""Projected Action -> Actual State Transformation Audit v0.

Observation-only replay on the same Fresh10.
At Day4 h11/h15/h19/h23, capture the self projected unit actions and observe
the public interpreter's sequential unit transformations.

No Candidate, no action mutation, no policy mutation.
"""
import copy,json,os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
TARGET_HOURS={11,15,19,23}
OUT=Path(f"projected_action_state_transformation_audit_v0_{SEED}.json")

_current_day=-1
_current_hour=-1
_self_farm_id=None
_projected={}
_execution=defaultdict(list)


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def tile_at(farm,pos):
    if pos is None: return None
    x,y=int(pos[0]),int(pos[1])
    try:return copy.deepcopy(farm["tiles"][y][x])
    except Exception:return None


def unit_positions(me):
    return [tuple(me["farmer"])] + [tuple(x) for x in (me.get("hands",[]) or [])]


def melon_day4_count(farm):
    n=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if (isinstance(t,dict) and t.get("kind")=="PLANT"
                and t.get("crop")=="MELON"
                and int(t.get("planted_day",-999))==4):
                n+=1
    return n


def reason_for_noop(before_tile,before_inv,before_seeds,effective_action,projected_action):
    if projected_action and projected_action[0]=="PLANT":
        crop=projected_action[1] if len(projected_action)>1 else None
        if effective_action and effective_action[0]=="PASS":
            return "ATOMIC_PLANT_BLOCKED_OR_FILTERED"
        if before_tile is not None:
            return "TARGET_TILE_NOT_EMPTY"
        if int(before_seeds.get(crop,0) or 0)<=0:
            return "NO_SEED"
        return "PLANT_NO_STATE_CHANGE_OTHER"
    if projected_action and projected_action[0]=="HARVEST":
        if not isinstance(before_tile,dict):
            return "NO_HARVESTABLE_TILE"
        if int(before_tile.get("yield_units",0) or 0)<=0:
            return "NO_YIELD"
        return "HARVEST_NO_STATE_CHANGE_OTHER"
    return "NO_STATE_CHANGE"


def wrapped_apply(original):
    def inner(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity=100):
        global _current_day,_current_hour,_self_farm_id
        is_self=(id(farm)==_self_farm_id)
        pos=kg._farmer_position(farm,idx)
        before_tile=tile_at(farm,pos)
        before_seeds=copy.deepcopy(private.get("seeds",{}) or {})
        invs=private.get("inventories",[]) or []
        before_inv=copy.deepcopy(invs[idx] if 0<=idx<len(invs) else {})
        key=(_current_day,_current_hour)
        projected_action=None
        if is_self and key in _projected:
            units=_projected[key]["unit_actions"]
            if 0<=idx<len(units):
                projected_action=copy.deepcopy(units[idx])

        original(farm,private,idx,action,board_size,day,turns_per_day,shed_capacity)

        after_pos=kg._farmer_position(farm,idx)
        after_tile=tile_at(farm,after_pos)
        after_seeds=copy.deepcopy(private.get("seeds",{}) or {})
        invs2=private.get("inventories",[]) or []
        after_inv=copy.deepcopy(invs2[idx] if 0<=idx<len(invs2) else {})

        if is_self and int(day)==4 and _current_hour in TARGET_HOURS:
            changed=(
                before_tile!=after_tile or before_seeds!=after_seeds
                or before_inv!=after_inv or tuple(pos or ())!=tuple(after_pos or ())
            )
            success=False
            if projected_action:
                op=projected_action[0]
                if op=="PLANT" and len(projected_action)>1:
                    crop=projected_action[1]
                    success=(
                        isinstance(after_tile,dict)
                        and after_tile.get("kind")=="PLANT"
                        and after_tile.get("crop")==crop
                        and before_tile is None
                    )
                elif op=="HARVEST":
                    success=(before_inv!=after_inv or before_tile!=after_tile)
                elif op in ("NORTH","SOUTH","EAST","WEST"):
                    success=tuple(pos or ())!=tuple(after_pos or ())
                elif op=="WATER":
                    success=isinstance(after_tile,dict) and bool(after_tile.get("watered_today",False))
                else:
                    success=changed
            reason=None if success else reason_for_noop(
                before_tile,before_inv,before_seeds,action,projected_action
            )
            _execution[key].append({
                "unit_index":idx,
                "projected_action":projected_action,
                "effective_action_seen_by_apply":copy.deepcopy(action),
                "position_before":list(pos) if pos is not None else None,
                "position_after":list(after_pos) if after_pos is not None else None,
                "tile_before":plain(before_tile),
                "tile_after":plain(after_tile),
                "seed_before":plain(before_seeds),
                "seed_after":plain(after_seeds),
                "inventory_before":plain(before_inv),
                "inventory_after":plain(after_inv),
                "success":bool(success),
                "state_changed":bool(changed),
                "noop_reason":reason,
            })
    return inner


def main():
    global _current_day,_current_hour,_self_farm_id
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    _self_farm_id=id(env.state[0].observation.farms[SEAT])

    def observed(obs):
        global _current_day,_current_hour,_self_farm_id
        _current_day=int(obs.get("day",-1)); _current_hour=int(obs.get("hour",-1))
        me=obs["farms"][obs["player"]]
        _self_farm_id=id(me)
        action=body_only.agent(obs)
        if _current_day==4 and _current_hour in TARGET_HOURS:
            units=[copy.deepcopy(action.get("farmer",["PASS"]))]
            units.extend(copy.deepcopy(action.get("hands",[]) or []))
            _projected[(_current_day,_current_hour)]={
                "cash":float(me.get("money",0) or 0),
                "unit_positions":[list(x) for x in unit_positions(me)],
                "melon_seed_stock":int((obs.get("private",{}).get("seeds",{}) or {}).get("MELON",0) or 0),
                "day4_melon_count_before":melon_day4_count(me),
                "action":copy.deepcopy(action),
                "unit_actions":units,
            }
        return action

    original_apply=kg._apply_unit_action
    kg._apply_unit_action=wrapped_apply(original_apply)
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=observed
        env.run(players)
    finally:
        kg._apply_unit_action=original_apply

    rows=[]
    for h in sorted(TARGET_HOURS):
        k=(4,h)
        p=_projected.get(k)
        ex=_execution.get(k,[])
        plant_req=[e for e in ex if e.get("projected_action") and e["projected_action"][0]=="PLANT"]
        melon_req=[e for e in plant_req if len(e["projected_action"])>1 and e["projected_action"][1]=="MELON"]
        wheat_req=[e for e in plant_req if len(e["projected_action"])>1 and e["projected_action"][1]=="WHEAT"]
        rows.append({
            "day":4,"hour":h,
            "projected":p,
            "execution":ex,
            "plant_summary":{
                "plant_requests":len(plant_req),
                "plant_successes":sum(e["success"] for e in plant_req),
                "melon_requests":len(melon_req),
                "melon_successes":sum(e["success"] for e in melon_req),
                "melon_noops":sum(not e["success"] for e in melon_req),
                "wheat_requests":len(wheat_req),
                "wheat_successes":sum(e["success"] for e in wheat_req),
                "noop_reasons":{
                    r:sum((not e["success"] and e["noop_reason"]==r) for e in plant_req)
                    for r in sorted(set(e["noop_reason"] for e in plant_req if e["noop_reason"]))
                },
            }
        })

    payload={
        "schema":"kaggriculture.strong-origin-v2.projected-action-state-transformation-audit.v0",
        "seed":SEED,"seat":SEAT,
        "policy_mutated":False,
        "rows":rows,
        "terminal":{
            "self":float(env.state[SEAT].reward),
            "opponent":float(env.state[1-SEAT].reward),
            "margin":float(env.state[SEAT].reward)-float(env.state[1-SEAT].reward),
        },
        "boundary":[
            "Observed projected actions are unchanged.",
            "Execution is recorded in the public interpreter's actual unit order.",
            "A PLANT success requires the intended crop to appear on the target tile after that unit executes.",
            "No Candidate, Direction, or policy mutation."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PROJECTED_ACTION_STATE_TRANSFORMATION "+json.dumps({
        "seed":SEED,
        "hours":{str(r["hour"]):r["plant_summary"] for r in rows},
        "terminal":payload["terminal"],
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
