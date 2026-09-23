#!/usr/bin/env python3
"""LAND Movement Convergence -> Duplicate PLANT Observer v0.

Exact SB-01 baseline replay. No policy mutation.

For duplicate-PLANT execution-loss events in turns +1..+72 after first realized
LAND expansion, connect only the immediately preceding transition:

  t-1 pre positions/actions
    -> positions at PLANT pre-State (co-location)
    -> duplicate PLANT requests on one tile at t
    -> first PLANT succeeds, later PLANT requests fail

This observer does NOT infer why a movement target was chosen. It records:
- duplicate PLANT group size/crop mix
- how many group members were already on the tile before t-1
- how many moved into that tile during t-1
- their exact t-1 actions
- whether the tile was empty before t-1 and immediately before PLANT

No Candidate or causal label is emitted.
"""
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from analyze_sb01_economic_layers_v0 import CROPS

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
WINDOW=72
OUT=Path(f"land_movement_convergence_duplicate_plant_v0_{SEED}.json")
MOVES={"NORTH":(0,-1),"SOUTH":(0,1),"EAST":(1,0),"WEST":(-1,0)}

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

def side_rows(steps,seat):
    out=[]
    for i,step in enumerate(steps):
        if not isinstance(step,(list,tuple)) or len(step)<=seat: continue
        obs=plain(getv(step[seat],"observation"))
        if not isinstance(obs,dict) or "farms" not in obs: continue
        out.append({"step_index":i,"obs":obs,"action":plain(getv(step[seat],"action"))})
    return out

def farm(obs):
    return obs["farms"][int(obs["player"])]

def positions(obs):
    f=farm(obs)
    return [list(f.get("farmer",[0,0]))]+[list(p) for p in (f.get("hands",[]) or [])]

def actions(action):
    if not isinstance(action,dict): return []
    return [action.get("farmer",["PASS"])]+list(action.get("hands",[]) or [])

def tile_at(obs,pos):
    x,y=pos
    return farm(obs)["tiles"][y][x]

def tile_desc(tile):
    if tile is None:return "EMPTY"
    if tile=="LOCKED":return "LOCKED"
    if isinstance(tile,dict):
        if tile.get("crop"):return "PLANT:"+str(tile.get("crop"))
        if tile.get("animal"):return "ANIMAL:"+str(tile.get("animal"))
        return str(tile.get("kind","DICT"))
    return str(tile)

def unlocked_count(obs):
    return sum(1 for row in farm(obs).get("tiles",[]) or [] for t in row if t!="LOCKED")

def first_land_i(rows):
    for i in range(1,len(rows)):
        if unlocked_count(rows[i]["obs"]) > unlocked_count(rows[i-1]["obs"]):
            return i
    return None

def duplicate_groups(pre_obs,action):
    """PLANT groups on same pre-State position with >=2 requests.

    Seed-atomic blocks are excluded because no first PLANT would execute.
    Pre-existing nonempty targets are excluded; focus is the known same-turn
    initially-empty target competition.
    """
    pos=positions(pre_obs); acts=actions(action)
    seeds=(pre_obs.get("private",{}) or {}).get("seeds",{}) or {}
    demand=Counter()
    for a in acts:
        if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
            demand[a[1]]+=1
    blocked={c for c,n in demand.items() if n>int(seeds.get(c,0) or 0)}

    bypos={}
    for idx,a in enumerate(acts):
        if idx>=len(pos) or not isinstance(a,list) or len(a)<2 or a[0]!="PLANT" or a[1] not in CROPS:
            continue
        crop=a[1]
        if crop in blocked: continue
        p=tuple(pos[idx])
        if tile_at(pre_obs,p) is not None: continue
        bypos.setdefault(p,[]).append({"unit_index":idx,"crop":crop,"action":a})
    return [
      {"target":list(p),"members":members}
      for p,members in bypos.items() if len(members)>=2
    ]

def expected_move(pre_pos,action):
    if not isinstance(action,list) or not action:return list(pre_pos)
    op=action[0]
    if op not in MOVES:return list(pre_pos)
    dx,dy=MOVES[op]
    return [pre_pos[0]+dx,pre_pos[1]+dy]

def observe_group(rows,j,group,rel):
    # duplicate PLANT is issued by rows[j].action from rows[j-1].obs.
    plant_pre=rows[j-1]["obs"]
    target=group["target"]
    current_positions=positions(plant_pre)

    prev_transition=None
    if j-2>=0:
        before_prev=rows[j-2]["obs"]
        prev_action=rows[j-1]["action"]
        prev_positions=positions(before_prev)
        prev_actions=actions(prev_action)
        members=[]
        moved_into=already_there=other=0
        for m in group["members"]:
            idx=m["unit_index"]
            cur=current_positions[idx] if idx<len(current_positions) else None
            pp=prev_positions[idx] if idx<len(prev_positions) else None
            pa=prev_actions[idx] if idx<len(prev_actions) else None
            if pp is None or cur is None:
                mode="missing"
            elif pp==target:
                mode="already_on_target"
                already_there+=1
            elif cur==target:
                mode="moved_into_target"
                moved_into+=1
            else:
                mode="other"
                other+=1
            members.append({
              "unit_index":idx,
              "crop_at_t":m["crop"],
              "position_before_t_minus_1":pp,
              "t_minus_1_action":pa,
              "expected_post_from_move":expected_move(pp,pa) if pp is not None else None,
              "position_at_plant_pre_state":cur,
              "arrival_mode":mode,
            })
        prev_transition={
          "target_tile_before_t_minus_1":tile_desc(tile_at(before_prev,target)),
          "target_tile_at_plant_pre_state":tile_desc(tile_at(plant_pre,target)),
          "moved_into_target_count":moved_into,
          "already_on_target_count":already_there,
          "other_count":other,
          "members":members,
        }

    crops=Counter(m["crop"] for m in group["members"])
    return {
      "relative_plant_turn":rel,
      "plant_action_step_index":rows[j]["step_index"],
      "target":target,
      "group_size":len(group["members"]),
      "crop_mix":dict(crops),
      "successful_first_unit_index":group["members"][0]["unit_index"],
      "failed_unit_indices":[m["unit_index"] for m in group["members"][1:]],
      "failed_count":len(group["members"])-1,
      "previous_transition":prev_transition,
    }

def build(rows):
    li=first_land_i(rows)
    if li is None:return {"land_event_found":False,"groups":[]}
    end=min(len(rows)-1,li+WINDOW)
    groups=[]
    for j in range(li+1,end+1):
        for g in duplicate_groups(rows[j-1]["obs"],rows[j]["action"]):
            groups.append(observe_group(rows,j,g,j-li))
    lo=rows[li]["obs"]
    return {
      "land_event_found":True,
      "land_event":{"step_index":rows[li]["step_index"],"day":int(lo.get("day",0) or 0),"hour":int(lo.get("hour",0) or 0)},
      "window_turns":end-li,
      "groups":groups,
    }

def compact(side):
    gs=side.get("groups",[])
    return {
      "duplicate_groups":len(gs),
      "failed_plants":sum(g["failed_count"] for g in gs),
      "group_size":dict(Counter(str(g["group_size"]) for g in gs)),
      "all_members_moved_into":sum(
        bool(g.get("previous_transition")) and
        g["previous_transition"]["moved_into_target_count"]==g["group_size"]
        for g in gs
      ),
      "mixed_arrival_groups":sum(
        bool(g.get("previous_transition")) and
        0<g["previous_transition"]["moved_into_target_count"]<g["group_size"]
        for g in gs
      ),
      "all_already_groups":sum(
        bool(g.get("previous_transition")) and
        g["previous_transition"]["already_on_target_count"]==g["group_size"]
        for g in gs
      ),
      "target_empty_before_t_minus_1":sum(
        bool(g.get("previous_transition")) and
        g["previous_transition"]["target_tile_before_t_minus_1"]=="EMPTY"
        for g in gs
      ),
    }

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT]; players[SEAT]=combat.agent
    env.run(players)
    steps=getattr(env,"steps",[]) or []
    s=build(side_rows(steps,SEAT)); o=build(side_rows(steps,1-SEAT))
    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.land-movement-convergence-duplicate-plant.v0",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "self":s,"opponent":o,
      "boundary":[
        "Exact SB-01 baseline policy/runtime; no Candidate or Action mutation.",
        "Duplicate group means >=2 non-atomic-blocked PLANT requests from units co-located on the same initially-empty tile.",
        "The immediately preceding transition is observed from recorded unit positions and issued actions.",
        "moved_into_target means the unit was elsewhere before t-1 and is on the duplicate target at PLANT pre-State.",
        "No claim is made about why that target was selected.",
        "No coordination fix or terminal benefit is inferred."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_MOVEMENT_CONVERGENCE_DUPLICATE_PLANT "+json.dumps({
      "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
      "self":compact(s),"opponent":compact(o),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
