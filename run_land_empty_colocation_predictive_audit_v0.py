#!/usr/bin/env python3
"""LAND Empty Co-location Predictive Audit v0.

Exact SB-01 baseline replay. No policy mutation.

Denominator audit for the previously observed duplicate-PLANT pathway.

After first realized LAND expansion (+72 turns):
- enumerate every onset episode where >=2 units are co-located on the same
  EMPTY tile;
- inspect the next two actions (same day only);
- record whether a valid duplicate PLANT execution-loss group appears on that
  tile.

The two-action horizon is grounded in the prior v1 observation: all 242 known
duplicate groups followed full co-location within 0-1 persistence turns.

No reason for target choice and no intervention are inferred.
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
LOOKAHEAD_ACTIONS=2
OUT=Path(f"land_empty_colocation_predictive_audit_v0_{SEED}.json")

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

def tile_at(obs,p):
    x,y=p
    return farm(obs)["tiles"][y][x]

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

def empty_colocations(obs):
    ps=positions(obs)
    bypos={}
    for idx,p in enumerate(ps):
        if tile_at(obs,p) is None:
            bypos.setdefault(tuple(p),[]).append(idx)
    return {p:ids for p,ids in bypos.items() if len(ids)>=2}

def valid_duplicate_at(rows,action_i,target):
    if action_i<=0 or action_i>=len(rows): return None
    pre=rows[action_i-1]["obs"]
    if int(pre.get("day",0) or 0)!=int(rows[action_i]["obs"].get("day",0) or 0) and False:
        pass
    ps=positions(pre); acts=actions(rows[action_i]["action"])
    seeds=(pre.get("private",{}) or {}).get("seeds",{}) or {}
    demand=Counter()
    for a in acts:
        if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:
            demand[a[1]]+=1
    blocked={c for c,n in demand.items() if n>int(seeds.get(c,0) or 0)}

    members=[]
    for idx,a in enumerate(acts):
        if idx>=len(ps) or ps[idx]!=list(target): continue
        if not isinstance(a,list) or len(a)<2 or a[0]!="PLANT" or a[1] not in CROPS: continue
        if a[1] in blocked: continue
        members.append({"unit_index":idx,"crop":a[1]})
    if len(members)<2:return None
    return {
      "action_step_index":rows[action_i]["step_index"],
      "members":members,
      "group_size":len(members),
      "failed_count":len(members)-1,
      "crop_mix":dict(Counter(m["crop"] for m in members)),
    }

def build(rows):
    li=first_land_i(rows)
    if li is None:return {"land_event_found":False,"episodes":[]}
    end=min(len(rows)-1,li+WINDOW)
    episodes=[]
    prev_active=set()
    for state_i in range(li,end+1):
        obs=rows[state_i]["obs"]
        day=int(obs.get("day",0) or 0)
        current=empty_colocations(obs)
        current_keys=set(current.keys())
        onsets=current_keys-prev_active
        for target in sorted(onsets):
            ids=current[target]
            outcome=None
            for delay in range(LOOKAHEAD_ACTIONS):
                action_i=state_i+1+delay
                if action_i>=len(rows):break
                pre_i=action_i-1
                if int(rows[pre_i]["obs"].get("day",0) or 0)!=day:
                    break
                d=valid_duplicate_at(rows,action_i,target)
                if d:
                    outcome={"delay_actions":delay,"duplicate":d}
                    break
            episodes.append({
              "onset_state_step_index":rows[state_i]["step_index"],
              "day":day,
              "hour":int(obs.get("hour",0) or 0),
              "target":list(target),
              "member_indices":ids,
              "group_size_at_onset":len(ids),
              "duplicate_within_2_actions":outcome is not None,
              "outcome":outcome,
            })
        # Reset episode continuity across day boundary because hand identities reset.
        next_same_day=(state_i+1<len(rows) and int(rows[state_i+1]["obs"].get("day",0) or 0)==day)
        prev_active=current_keys if next_same_day else set()
    lo=rows[li]["obs"]
    return {
      "land_event_found":True,
      "land_event":{"step_index":rows[li]["step_index"],"day":int(lo.get("day",0) or 0),"hour":int(lo.get("hour",0) or 0)},
      "episodes":episodes,
    }

def compact(side):
    es=side.get("episodes",[])
    hit=[e for e in es if e["duplicate_within_2_actions"]]
    return {
      "episodes":len(es),
      "hit_episodes":len(hit),
      "hit_rate":(len(hit)/len(es) if es else None),
      "delay_actions":dict(Counter(str(e["outcome"]["delay_actions"]) for e in hit)),
      "failed_plants_from_hits":sum(e["outcome"]["duplicate"]["failed_count"] for e in hit),
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
      "schema":"kaggriculture.land-empty-colocation-predictive-audit.v0",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "self":s,"opponent":o,
      "boundary":[
        "Exact SB-01 baseline policy/runtime; no Candidate or Action mutation.",
        "Denominator is onset episodes with >=2 units co-located on the same empty tile.",
        "Episode continuity resets at day boundary because hand identities reset.",
        "Outcome asks only whether a valid duplicate PLANT group occurs on that tile within the next two same-day actions.",
        "No target-selection intent, cause, or terminal benefit is inferred."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_EMPTY_COLOCATION_PREDICTIVE_AUDIT "+json.dumps({
      "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
      "self":compact(s),"opponent":compact(o),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
