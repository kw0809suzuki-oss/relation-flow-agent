#!/usr/bin/env python3
"""LAND Co-location Onset -> Duplicate PLANT Observer v1.

Exact SB-01 baseline replay. No policy mutation.

For each duplicate-PLANT group in turns +1..+72 after first realized LAND:
1) identify the unit indices co-located on one initially-empty target at PLANT time;
2) stay within the same game day;
3) walk backward through the contiguous suffix in which all of those units were
   already co-located on that target;
4) record the onset transition that first produced full co-location;
5) record how many turns full co-location persisted before duplicate PLANT.

This avoids assuming that convergence always happened exactly one turn earlier.
Unit identity is not carried across day boundaries because hands reset daily.

No target-selection intent, cause, or Candidate is inferred.
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
OUT=Path(f"land_colocation_onset_duplicate_plant_v1_{SEED}.json")

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

def farm(obs): return obs["farms"][int(obs["player"])]

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

def duplicate_groups(pre_obs,action):
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
    return [{"target":list(p),"members":m} for p,m in bypos.items() if len(m)>=2]

def all_members_at(rows,row_i,member_indices,target):
    if row_i<0:return False
    ps=positions(rows[row_i]["obs"])
    for idx in member_indices:
        if idx>=len(ps) or ps[idx]!=target:
            return False
    return True

def onset_for_group(rows,plant_action_i,group):
    # PLANT pre-State is rows[plant_action_i-1].obs.
    plant_pre_i=plant_action_i-1
    target=group["target"]
    ids=[m["unit_index"] for m in group["members"]]
    plant_day=int(rows[plant_pre_i]["obs"].get("day",0) or 0)

    onset_i=plant_pre_i
    while onset_i-1>=0:
        prev_day=int(rows[onset_i-1]["obs"].get("day",0) or 0)
        if prev_day!=plant_day: break
        if not all_members_at(rows,onset_i-1,ids,target): break
        onset_i-=1

    duration=plant_pre_i-onset_i
    onset_obs=rows[onset_i]["obs"]
    before_i=onset_i-1
    before_obs=rows[before_i]["obs"] if before_i>=0 else None
    onset_action=rows[onset_i]["action"] if onset_i>=0 else None
    before_positions=positions(before_obs) if before_obs is not None else []
    onset_positions=positions(onset_obs)
    onset_actions=actions(onset_action)

    members=[]
    moved=already=new_unit=other=0
    for m in group["members"]:
        idx=m["unit_index"]
        now=onset_positions[idx] if idx<len(onset_positions) else None
        before=before_positions[idx] if idx<len(before_positions) else None
        act=onset_actions[idx] if idx<len(onset_actions) else None
        if before is None and now==target:
            mode="new_unit_at_target"; new_unit+=1
        elif before==target and now==target:
            mode="already_on_target"; already+=1
        elif before is not None and before!=target and now==target:
            mode="moved_into_target"; moved+=1
        else:
            mode="other"; other+=1
        members.append({
          "unit_index":idx,
          "crop_at_plant":m["crop"],
          "position_before_onset":before,
          "onset_action":act,
          "position_after_onset":now,
          "arrival_mode":mode,
        })

    return {
      "onset_relative_to_plant_pre_state":onset_i-plant_pre_i,
      "full_colocation_persistence_turns_before_plant":duration,
      "onset_step_index":rows[onset_i]["step_index"],
      "onset_day":int(onset_obs.get("day",0) or 0),
      "onset_hour":int(onset_obs.get("hour",0) or 0),
      "target_tile_before_onset":tile_desc(tile_at(before_obs,target)) if before_obs is not None else None,
      "target_tile_after_onset":tile_desc(tile_at(onset_obs,target)),
      "moved_into_target_count":moved,
      "already_on_target_count":already,
      "new_unit_at_target_count":new_unit,
      "other_count":other,
      "members":members,
    }

def observe_group(rows,j,g,rel):
    onset=onset_for_group(rows,j,g)
    crops=Counter(m["crop"] for m in g["members"])
    return {
      "relative_plant_turn":rel,
      "plant_action_step_index":rows[j]["step_index"],
      "target":g["target"],
      "group_size":len(g["members"]),
      "crop_mix":dict(crops),
      "failed_count":len(g["members"])-1,
      "unit_indices":[m["unit_index"] for m in g["members"]],
      "colocation_onset":onset,
    }

def build(rows):
    li=first_land_i(rows)
    if li is None:return {"land_event_found":False,"groups":[]}
    end=min(len(rows)-1,li+WINDOW)
    gs=[]
    for j in range(li+1,end+1):
        for g in duplicate_groups(rows[j-1]["obs"],rows[j]["action"]):
            gs.append(observe_group(rows,j,g,j-li))
    lo=rows[li]["obs"]
    return {
      "land_event_found":True,
      "land_event":{"step_index":rows[li]["step_index"],"day":int(lo.get("day",0) or 0),"hour":int(lo.get("hour",0) or 0)},
      "window_turns":end-li,
      "groups":gs,
    }

def compact(side):
    gs=side.get("groups",[])
    return {
      "groups":len(gs),
      "failed_plants":sum(g["failed_count"] for g in gs),
      "persistence_turns":dict(Counter(str(g["colocation_onset"]["full_colocation_persistence_turns_before_plant"]) for g in gs)),
      "onset_moved_members":sum(g["colocation_onset"]["moved_into_target_count"] for g in gs),
      "onset_already_members":sum(g["colocation_onset"]["already_on_target_count"] for g in gs),
      "onset_new_unit_members":sum(g["colocation_onset"]["new_unit_at_target_count"] for g in gs),
      "onset_target_empty":sum(g["colocation_onset"]["target_tile_before_onset"]=="EMPTY" for g in gs),
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
      "schema":"kaggriculture.land-colocation-onset-duplicate-plant.v1",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "self":s,"opponent":o,
      "boundary":[
        "Exact SB-01 baseline policy/runtime; no Candidate or Action mutation.",
        "Backtracking is limited to the same game day because hand identities reset daily.",
        "Co-location onset is the earliest row in the same-day contiguous suffix where all duplicate-PLANT units occupy the final target tile.",
        "Movement/action at onset is observed; target-selection intent is not inferred.",
        "No coordination fix or terminal-effect claim is generated."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_COLOCATION_ONSET_DUPLICATE_PLANT "+json.dumps({
      "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
      "self":compact(s),"opponent":compact(o),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
