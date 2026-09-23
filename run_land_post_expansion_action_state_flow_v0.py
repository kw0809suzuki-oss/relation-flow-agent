#!/usr/bin/env python3
"""LAND Post-Expansion Action-to-State Flow v0.

Exact SB-01 baseline replay. No policy mutation.

For the first realized LAND expansion of each side, inspect the next 72 turns.
Keep issued Action counts separate from directly observed productive State
transitions.

Question:
Is the post-Expansion productive gap already visible in what Actions are issued,
or do issued productive Actions fail to become productive State?

No cause/bottleneck label is emitted.
"""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from analyze_sb01_economic_layers_v0 import derive_side

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
WINDOW=72
OUT=Path(f"land_post_expansion_action_state_flow_v0_{SEED}.json")

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("COW","SHEEP","GOOSE")
MOVE={"NORTH","SOUTH","EAST","WEST"}

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

def compact_state(obs):
    d=derive_side(obs)
    cap=d["uncommitted_capacity"]
    unlocked=float(cap["unlocked_tiles"])
    empty=float(cap["empty_unlocked_tiles"])
    return {
      "day":int(d["day"]),"hour":int(d["hour"]),
      "cash":float(d["cash"]),
      "unlocked_tiles":unlocked,
      "empty_tiles":empty,
      "occupied_tiles":unlocked-empty,
      "crop_count":float(sum(d["committed_production"]["crop_count"].values())),
      "animal_count":float(sum(d["committed_production"]["animal_count"].values())),
      "hands":float(cap["current_hands"]),
      "seed_inventory_total":float(sum(d["seed_inventory_fact"].values())),
      "sellable_stock_total":float(sum(
          float(x.get("quantity",0) or 0)
          for x in d["liquidatable_inventory"]["by_item"].values()
      )),
      "committed_mark":float(d["committed_production"]["same_basis_subtotal"]),
    }

def side_obs_rows(steps,seat):
    out=[]
    for i,step in enumerate(steps):
        if not isinstance(step,(list,tuple)) or len(step)<=seat: continue
        obs=plain(getv(step[seat],"observation"))
        if not isinstance(obs,dict) or "farms" not in obs: continue
        out.append({"step_index":i,"obs":obs,"state":compact_state(obs),"action":plain(getv(step[seat],"action"))})
    return out

def first_land_i(rows):
    for i in range(1,len(rows)):
        if rows[i]["state"]["unlocked_tiles"] > rows[i-1]["state"]["unlocked_tiles"]:
            return i
    return None

def unit_actions(action):
    if not isinstance(action,dict): return []
    xs=[action.get("farmer")]
    xs.extend(action.get("hands",[]) or [])
    return [x for x in xs if isinstance(x,list) and x]

def action_counts(action):
    c=Counter()
    market=Counter()
    if isinstance(action,dict):
        for a in unit_actions(action):
            op=str(a[0])
            c[op]+=1
            if op=="PLANT" and len(a)>1: c[f"PLANT:{a[1]}"]+=1
            if op=="PLACE" and len(a)>1: c[f"PLACE:{a[1]}"]+=1
        for o in action.get("market",[]) or []:
            if not isinstance(o,list) or not o: continue
            op=str(o[0]); market[op]+=1
            if len(o)>1: market[f"{op}:{o[1]}"]+=1
    return c,market

def farm_for(obs):
    p=int(obs["player"])
    return obs["farms"][p]

def tile_product(tile):
    if not isinstance(tile,dict): return (None,None)
    return (tile.get("crop"), tile.get("animal"))

def observed_productive_additions(pre_obs,post_obs):
    pre=farm_for(pre_obs); post=farm_for(post_obs)
    crops=Counter(); animals=Counter()
    pre_tiles=pre.get("tiles",[]) or []; post_tiles=post.get("tiles",[]) or []
    for y in range(min(len(pre_tiles),len(post_tiles))):
        prow=pre_tiles[y] or []; qrow=post_tiles[y] or []
        for x in range(min(len(prow),len(qrow))):
            pc,pa=tile_product(prow[x]); qc,qa=tile_product(qrow[x])
            if qc in CROPS and qc!=pc: crops[qc]+=1
            if qa in ANIMALS and qa!=pa: animals[qa]+=1
    return crops,animals

def build(rows):
    li=first_land_i(rows)
    if li is None:
        return {"land_event_found":False}
    end=min(len(rows)-1,li+WINDOW)
    unit=Counter(); market=Counter(); added_crops=Counter(); added_animals=Counter()
    by_turn=[]
    for j in range(li+1,end+1):
        uc,mc=action_counts(rows[j]["action"])
        unit.update(uc); market.update(mc)
        cc,aa=observed_productive_additions(rows[j-1]["obs"],rows[j]["obs"])
        added_crops.update(cc); added_animals.update(aa)
        if cc or aa:
            by_turn.append({
              "relative_turn":j-li,
              "step_index":rows[j]["step_index"],
              "new_crops":dict(cc),
              "new_animals":dict(aa),
            })
    s0=rows[li]["state"]; se=rows[end]["state"]
    return {
      "land_event_found":True,
      "land_event":{"step_index":rows[li]["step_index"],"day":s0["day"],"hour":s0["hour"]},
      "window_turns":end-li,
      "issued_unit_actions":dict(unit),
      "issued_market_orders":dict(market),
      "observed_new_crops":dict(added_crops),
      "observed_new_animals":dict(added_animals),
      "productive_addition_events":by_turn,
      "state_t0":s0,
      "state_t72":se,
      "state_delta":{
        k:se[k]-s0[k] for k in (
          "cash","empty_tiles","occupied_tiles","crop_count","animal_count",
          "hands","seed_inventory_total","sellable_stock_total","committed_mark"
        )
      },
    }

def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    steps=getattr(env,"steps",[]) or []
    s=build(side_obs_rows(steps,SEAT))
    o=build(side_obs_rows(steps,1-SEAT))
    rewards=[float(x.reward) for x in env.state]
    payload={
      "schema":"kaggriculture.land-post-expansion-action-state-flow.v0",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "self":s,"opponent":o,
      "boundary":[
        "Exact SB-01 baseline policy/runtime; no Candidate or Action mutation.",
        "Window is turns +1..+72 after each side's own first realized LAND expansion.",
        "Issued Actions and directly observed new productive placements are separate outputs.",
        "Observed new crop/animal counts come from adjacent tile-State transitions, not Action labels.",
        "Net crop/animal State delta may differ from gross new placements because existing assets can disappear.",
        "No cause, binding constraint, strategy rule, or adoption judgment is emitted."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LAND_POST_EXPANSION_ACTION_STATE_FLOW "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "terminal":payload["terminal"],
      "self_land":s.get("land_event"),"opp_land":o.get("land_event"),
      "self_issued_plant":s.get("issued_unit_actions",{}).get("PLANT",0),
      "opp_issued_plant":o.get("issued_unit_actions",{}).get("PLANT",0),
      "self_new_crops":sum(s.get("observed_new_crops",{}).values()),
      "opp_new_crops":sum(o.get("observed_new_crops",{}).values()),
      "self_issued_place":s.get("issued_unit_actions",{}).get("PLACE",0),
      "opp_issued_place":o.get("issued_unit_actions",{}).get("PLACE",0),
      "self_new_animals":sum(s.get("observed_new_animals",{}).values()),
      "opp_new_animals":sum(o.get("observed_new_animals",{}).values()),
      "self_delta":s.get("state_delta"),"opp_delta":o.get("state_delta"),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
