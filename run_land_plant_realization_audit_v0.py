#!/usr/bin/env python3
"""LAND PLANT Realization Audit v0.

Exact SB-01 baseline replay. No policy mutation.

For every issued PLANT in turns +1..+72 after the first realized LAND expansion:
- align unit position and pre-State;
- apply the confirmed public PLANT rules mechanically;
- classify whether the request was blocked before execution, reached a nonempty
  target, or succeeded in the unit-action phase;
- separately record whether that successful plant is visible in the retained
  post-State.

Important public-rule facts:
- if total PLANT demand for a crop in one turn exceeds pre-turn seed inventory,
  ALL PLANT requests for that crop are atomically replaced by PASS;
- unit actions execute before market orders, so same-turn BUY_SEED cannot supply
  same-turn PLANT.

No causal/bottleneck label is emitted.
"""
import copy
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from analyze_sb01_economic_layers_v0 import CROPS

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
WINDOW=72
OUT=Path(f"land_plant_realization_audit_v0_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception: pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception: pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception: pass
    if hasattr(v,"__dict__"):
        try:return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception: pass
    return str(v)


def getv(s,k,default=None):
    if isinstance(s,dict): return s.get(k,default)
    try:return getattr(s,k)
    except Exception:return default


def unlocked_count(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    return sum(1 for row in farm.get("tiles",[]) or [] for tile in row if tile!="LOCKED")


def side_rows(steps,seat):
    out=[]
    for i,step in enumerate(steps):
        if not isinstance(step,(list,tuple)) or len(step)<=seat: continue
        obs=plain(getv(step[seat],"observation"))
        if not isinstance(obs,dict) or "farms" not in obs: continue
        out.append({"step_index":i,"obs":obs,"action":plain(getv(step[seat],"action"))})
    return out


def first_land_i(rows):
    for i in range(1,len(rows)):
        if unlocked_count(rows[i]["obs"]) > unlocked_count(rows[i-1]["obs"]):
            return i
    return None


def unit_positions(pre_obs):
    p=int(pre_obs["player"])
    farm=pre_obs["farms"][p]
    return [list(farm.get("farmer",[0,0]))]+[list(x) for x in (farm.get("hands",[]) or [])]


def unit_actions(action):
    if not isinstance(action,dict): return []
    return [action.get("farmer",["PASS"])]+list(action.get("hands",[]) or [])


def market_seed_orders(action):
    out=Counter()
    if not isinstance(action,dict): return out
    for o in action.get("market",[]) or []:
        if isinstance(o,list) and len(o)>=3 and o[0]=="BUY_SEED" and o[1] in CROPS:
            try:n=int(o[2])
            except Exception:n=0
            if n>0:out[o[1]]+=n
    return out


def tile_at(tiles,pos):
    x,y=pos
    if y<0 or y>=len(tiles): return "__OUT__"
    row=tiles[y] or []
    if x<0 or x>=len(row): return "__OUT__"
    return row[x]


def set_tile(tiles,pos,val):
    x,y=pos
    if 0<=y<len(tiles) and 0<=x<len(tiles[y]):
        tiles[y][x]=val


def tile_repr(tile):
    if tile is None:return "EMPTY"
    if tile=="LOCKED":return "LOCKED"
    if isinstance(tile,dict):
        if tile.get("crop"): return "PLANT:"+str(tile.get("crop"))
        if tile.get("animal"): return "ANIMAL:"+str(tile.get("animal"))
        return str(tile.get("kind","DICT"))
    return str(tile)


def shadow_turn(pre_obs,action,post_obs,relative_turn):
    p=int(pre_obs["player"])
    farm=pre_obs["farms"][p]
    private=pre_obs.get("private",{}) or {}
    tiles=copy.deepcopy(farm.get("tiles",[]) or [])
    positions=unit_positions(pre_obs)
    actions=unit_actions(action)
    pre_seeds={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
    seeds=dict(pre_seeds)
    same_turn_buy=dict(market_seed_orders(action))

    demand=Counter()
    for a in actions:
        if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
            demand[a[1]]+=1
    blocked={c for c,n in demand.items() if n>pre_seeds.get(c,0)}

    events=[]
    for idx,a in enumerate(actions):
        if not isinstance(a,list) or not a: continue
        op=a[0]
        pos=positions[idx] if idx<len(positions) else None
        if pos is None:
            if op=="PLANT" and len(a)>=2:
                events.append({
                    "relative_turn":relative_turn,"unit_index":idx,"crop":a[1],
                    "position":None,"classification":"missing_unit_position",
                    "pre_seed_for_crop":pre_seeds.get(a[1],0),
                    "turn_plant_demand_for_crop":demand.get(a[1],0),
                    "same_turn_buy_seed_issued":same_turn_buy.get(a[1],0),
                    "pre_target":"NO_UNIT","post_target":"NO_UNIT",
                    "visible_post_as_requested_crop":False,
                })
            continue

        before=tile_at(tiles,pos)

        if op=="PLANT" and len(a)>=2:
            crop=a[1]
            pre_original=tile_at(farm.get("tiles",[]) or [],pos)
            if crop not in CROPS:
                cls="invalid_crop"
            elif crop in blocked:
                cls="atomic_seed_blocked"
            elif before=="LOCKED":
                cls="target_locked"
            elif before is not None:
                if pre_original is None:
                    cls="same_turn_target_became_nonempty"
                else:
                    cls="target_nonempty_preexisting"
            elif seeds.get(crop,0)<=0:
                # Should be unreachable when demand <= pre-seed and no other seed consumer exists.
                cls="seed_exhausted_at_execution"
            else:
                cls="success_unit_phase"
                seeds[crop]-=1
                set_tile(tiles,pos,{
                    "kind":"PLANT","crop":crop,
                    "planted_day":int(pre_obs.get("day",0) or 0),
                    "yield_units":0 if CROPS[crop]["ongoing"] else 1,
                    "watered_today":False,
                })

            post_farm=post_obs["farms"][int(post_obs["player"])]
            post_tile=tile_at(post_farm.get("tiles",[]) or [],pos)
            visible=bool(isinstance(post_tile,dict) and post_tile.get("kind")=="PLANT" and post_tile.get("crop")==crop)
            events.append({
                "relative_turn":relative_turn,
                "unit_index":idx,
                "crop":crop,
                "position":pos,
                "classification":cls,
                "pre_seed_for_crop":pre_seeds.get(crop,0),
                "turn_plant_demand_for_crop":demand.get(crop,0),
                "same_turn_buy_seed_issued":same_turn_buy.get(crop,0),
                "pre_target":tile_repr(pre_original),
                "execution_target":tile_repr(before),
                "post_target":tile_repr(post_tile),
                "visible_post_as_requested_crop":visible,
            })
            continue

        # Minimal public-rule shadow for occupancy changes that can affect a
        # later PLANT request by another co-located unit.
        if before=="LOCKED":
            continue
        if op=="DIG":
            if before is None:
                continue
            if isinstance(before,dict) and "animal" in before:
                continue
            set_tile(tiles,pos,None)
        elif op=="BUILD_COOP":
            if before is None:set_tile(tiles,pos,{"kind":"COOP"})
        elif op=="BUILD_PASTURE":
            if before is None:set_tile(tiles,pos,{"kind":"PASTURE"})
        elif op=="HARVEST" and isinstance(before,dict) and before.get("kind")=="PLANT":
            crop=before.get("crop")
            if crop in CROPS and float(before.get("yield_units",0) or 0)>0:
                age=int(pre_obs.get("day",0) or 0)-int(before.get("planted_day",0) or 0)
                if age>=CROPS[crop]["first"]:
                    if not CROPS[crop]["ongoing"]:
                        set_tile(tiles,pos,None)

    return events


def build(rows):
    li=first_land_i(rows)
    if li is None:return {"land_event_found":False,"events":[]}
    end=min(len(rows)-1,li+WINDOW)
    events=[]
    for j in range(li+1,end+1):
        events.extend(shadow_turn(
            rows[j-1]["obs"],rows[j]["action"],rows[j]["obs"],j-li
        ))
    land_obs=rows[li]["obs"]
    return {
        "land_event_found":True,
        "land_event":{
            "step_index":rows[li]["step_index"],
            "day":int(land_obs.get("day",0) or 0),
            "hour":int(land_obs.get("hour",0) or 0),
        },
        "window_turns":end-li,
        "events":events,
    }


def compact(side):
    ev=side.get("events",[])
    cls=Counter(x["classification"] for x in ev)
    crops=Counter(x["crop"] for x in ev)
    vis=sum(bool(x.get("visible_post_as_requested_crop")) for x in ev)
    success=sum(x["classification"]=="success_unit_phase" for x in ev)
    return {
        "issued":len(ev),"classification":dict(cls),"crop":dict(crops),
        "success_unit_phase":success,"visible_post":vis,
        "same_turn_buy_on_atomic_blocks":sum(
            int(x.get("same_turn_buy_seed_issued",0) or 0)
            for x in ev if x["classification"]=="atomic_seed_blocked"
        ),
    }


def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    steps=getattr(env,"steps",[]) or []
    s=build(side_rows(steps,SEAT))
    o=build(side_rows(steps,1-SEAT))
    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.land-plant-realization-audit.v0",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "self":s,"opponent":o,
      "rule_provenance":"Kaggle/kaggle-environments kaggriculture.py @ b2405492c8403f6649f9317290f215e0290a2425",
      "boundary":[
        "Exact SB-01 baseline policy/runtime; no Candidate or Action mutation.",
        "Window is turns +1..+72 after each side's own first realized LAND expansion.",
        "PLANT classification uses confirmed public execution order and legality rules.",
        "Atomic seed blocking uses pre-turn seed inventory before market orders.",
        "same-turn BUY_SEED is recorded but never treated as available to same-turn PLANT.",
        "success_unit_phase means the PLANT passed the unit-action rules in the mechanical shadow.",
        "visible_post_as_requested_crop is a separate retained-State observation.",
        "No cause, bottleneck, strategy judgment, or adoption conclusion is emitted."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_PLANT_REALIZATION_AUDIT "+json.dumps({
      "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
      "self_land":s.get("land_event"),"opp_land":o.get("land_event"),
      "self":compact(s),"opponent":compact(o),
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
