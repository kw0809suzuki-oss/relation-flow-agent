#!/usr/bin/env python3
"""LAND Transition Action Bridge v0.

Exact SB-01 baseline replay. No policy mutation.

Purpose:
After LAND Productive Transition Observer v0 found the first event-aligned
physical State divergence at t=+1, expose only the immediately adjacent
pre-State -> Action -> post-State transitions.

Alignment is already established:
  row i-1 observation -> row i.action -> row i observation

No cause label is emitted.
"""
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from analyze_sb01_economic_layers_v0 import derive_side

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"land_transition_action_bridge_v0_{SEED}.json")
REL_TRANSITIONS=(-1,0,1,2)


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
    occupied=unlocked-empty
    return {
      "day":int(d["day"]),
      "hour":int(d["hour"]),
      "cash":float(d["cash"]),
      "unlocked_tiles":unlocked,
      "empty_tiles":empty,
      "occupied_tiles":occupied,
      "crop_count":float(sum(d["committed_production"]["crop_count"].values())),
      "animal_count":float(sum(d["committed_production"]["animal_count"].values())),
      "hands":float(cap["current_hands"]),
      "seed_inventory_total":float(sum(d["seed_inventory_fact"].values())),
      "sellable_stock_total":float(sum(
          float(x.get("quantity",0) or 0)
          for x in d["liquidatable_inventory"]["by_item"].values()
      )),
      "committed_mark":float(d["committed_production"]["same_basis_subtotal"]),
      "crop_count_by_type":dict(d["committed_production"]["crop_count"]),
      "animal_count_by_type":dict(d["committed_production"]["animal_count"]),
      "seed_inventory_by_type":dict(d["seed_inventory_fact"]),
      "sellable_stock_by_item":{
          k:float(v.get("quantity",0) or 0)
          for k,v in d["liquidatable_inventory"]["by_item"].items()
      },
    }


def side_rows(steps,seat):
    rows=[]
    for i,step in enumerate(steps):
        if not isinstance(step,(list,tuple)) or len(step)<=seat: continue
        obs=plain(getv(step[seat],"observation"))
        if not isinstance(obs,dict) or "farms" not in obs: continue
        rows.append({
          "step_index":i,
          "state":compact_state(obs),
          "action":plain(getv(step[seat],"action")),
        })
    return rows


def first_land_row(rows):
    for i in range(1,len(rows)):
        if rows[i]["state"]["unlocked_tiles"] > rows[i-1]["state"]["unlocked_tiles"]:
            return i
    return None


def state_delta(pre,post):
    fields=("cash","unlocked_tiles","empty_tiles","occupied_tiles","crop_count","animal_count",
            "hands","seed_inventory_total","sellable_stock_total","committed_mark")
    return {f:post[f]-pre[f] for f in fields}


def transition(rows,land_i,rel):
    # rel=0 is the LAND-causing transition ending at t=0 State.
    cur_i=land_i+rel
    pre_i=cur_i-1
    if pre_i<0 or cur_i<0 or cur_i>=len(rows): return None
    pre=rows[pre_i]; cur=rows[cur_i]
    return {
      "relative_transition":rel,
      "pre_step_index":pre["step_index"],
      "action_step_index":cur["step_index"],
      "pre_state":pre["state"],
      "action":cur["action"],
      "post_state":cur["state"],
      "state_delta":state_delta(pre["state"],cur["state"]),
    }


def summarize_action(action):
    if not isinstance(action,dict): return {"market":[],"farmer":"NONE","hands":[]}
    market=[]
    for o in action.get("market",[]) or []:
        if isinstance(o,(list,tuple)):
            market.append(":".join(str(x) for x in o[:3]))
        else:
            market.append(str(o))
    def key(a):
        if isinstance(a,(list,tuple)): return ":".join(str(x) for x in a[:3])
        if a is None:return "NONE"
        return str(a)
    return {
      "market":market,
      "farmer":key(action.get("farmer")),
      "hands":[key(a) for a in (action.get("hands",[]) or [])],
    }


def build(rows):
    li=first_land_row(rows)
    if li is None:
        return {"land_event_found":False,"land_event":None,"transitions":{}}
    s=rows[li]["state"]; p=rows[li-1]["state"]
    trs={}
    for rel in REL_TRANSITIONS:
        t=transition(rows,li,rel)
        if t:
            t["action_summary"]=summarize_action(t["action"])
        trs[str(rel)]=t
    return {
      "land_event_found":True,
      "land_event":{
        "step_index":rows[li]["step_index"],
        "day":s["day"],"hour":s["hour"],
        "unlocked_before":p["unlocked_tiles"],
        "unlocked_after":s["unlocked_tiles"],
      },
      "transitions":trs,
    }


def main():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[base.OPPONENT,base.OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)

    steps=getattr(env,"steps",[]) or []
    sr=side_rows(steps,SEAT)
    orows=side_rows(steps,1-SEAT)
    sout=build(sr); oout=build(orows)
    rewards=[float(x.reward) for x in env.state]

    payload={
      "schema":"kaggriculture.land-transition-action-bridge.v0",
      "seed":SEED,"seat":SEAT,"policy_mutated":False,
      "terminal":{
        "self":rewards[SEAT],"opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
      },
      "self":sout,
      "opponent":oout,
      "boundary":[
        "Exact SB-01 baseline policy/runtime is reused.",
        "No Candidate, threshold, strategy rule, or Action change is introduced.",
        "row i-1 observation -> row i.action -> row i observation alignment is used.",
        "relative transition 0 is the realized first LAND expansion transition.",
        "Only relative transitions -1,0,+1,+2 are retained.",
        "Raw issued Action and direct State delta are recorded; no execution success is inferred beyond observed State change.",
        "No cause label, bottleneck label, or strategy judgment is emitted."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    print("LAND_TRANSITION_ACTION_BRIDGE "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "terminal":payload["terminal"],
      "self_land":sout["land_event"],
      "opp_land":oout["land_event"],
      "self_t1":sout["transitions"].get("1",{}).get("action_summary") if sout["land_event_found"] else None,
      "opp_t1":oout["transitions"].get("1",{}).get("action_summary") if oout["land_event_found"] else None,
      "self_t1_delta":sout["transitions"].get("1",{}).get("state_delta") if sout["land_event_found"] else None,
      "opp_t1_delta":oout["transitions"].get("1",{}).get("state_delta") if oout["land_event_found"] else None,
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
