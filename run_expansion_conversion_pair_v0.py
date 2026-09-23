#!/usr/bin/env python3
"""Paired Battle: Expansion Conversion Model v0 vs current baseline.

Terminal authority first. Post-LAND C->R observations are secondary.
"""
import json, os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import whole_flow_control_agent as baseline
import expansion_conversion_v0 as candidate
import run_land_post_expansion_action_state_flow_v0 as flow
import run_land_plant_realization_audit_v0 as plant_audit

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"expansion_conversion_pair_v0_{SEED}.json")


def configure(agent):
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.set_control_enabled(False)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def plant_summary(steps):
    x=plant_audit.build(plant_audit.side_rows(steps,SEAT))
    ev=x.get("events",[]) or []
    cls=Counter(e.get("classification") for e in ev)
    return {
      "issued":len(ev),
      "success_unit_phase":cls.get("success_unit_phase",0),
      "same_turn_target_became_nonempty":cls.get("same_turn_target_became_nonempty",0),
      "atomic_seed_blocked":cls.get("atomic_seed_blocked",0),
      "target_nonempty_preexisting":cls.get("target_nonempty_preexisting",0),
    }


def flow_summary(steps):
    x=flow.build(flow.side_obs_rows(steps,SEAT))
    if not x.get("land_event_found"):
        return {"land_event_found":False}
    d=x.get("state_delta",{}) or {}
    return {
      "land_event_found":True,
      "land_event":x.get("land_event"),
      "plant_issued":(x.get("issued_unit_actions") or {}).get("PLANT",0),
      "new_crops":sum((x.get("observed_new_crops") or {}).values()),
      "new_animals":sum((x.get("observed_new_animals") or {}).values()),
      "occupied_delta":d.get("occupied_tiles"),
      "crop_delta":d.get("crop_count"),
      "animal_delta":d.get("animal_count"),
      "committed_delta":d.get("committed_mark"),
      "cash_delta":d.get("cash"),
    }


def run(agent):
    configure(agent)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=agent.agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    steps=getattr(env,"steps",[]) or []
    return {
      "self":rewards[SEAT],
      "opponent":rewards[1-SEAT],
      "margin":rewards[SEAT]-rewards[1-SEAT],
      "win":rewards[SEAT]>rewards[1-SEAT],
      "post_land_flow":flow_summary(steps),
      "post_land_plant":plant_summary(steps),
    }


b=run(baseline)
c=run(candidate)
payload={
  "schema":"kaggriculture.expansion-conversion.paired.v0",
  "seed":SEED,"seat":SEAT,
  "baseline":b,"candidate":c,
  "delta_self":c["self"]-b["self"],
  "delta_opponent":c["opponent"]-b["opponent"],
  "delta_margin":c["margin"]-b["margin"],
  "boundary":[
    "Terminal self/margin/wins are adoption authority.",
    "Only crop-lane work-target reservation after realized first LAND expansion differs.",
    "Crop targets, scores, seed buying, HIRE, LAND, livestock, D14 closure and other market rules are unchanged.",
    "Post-LAND C->R measurements are secondary mechanism checks, not adoption authority.",
    "No rescue condition is added after this paired Battle."
  ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("EXPANSION_CONVERSION_PAIR "+json.dumps({
  "seed":SEED,"seat":SEAT,
  "baseline_terminal":{k:b[k] for k in ("self","opponent","margin","win")},
  "candidate_terminal":{k:c[k] for k in ("self","opponent","margin","win")},
  "delta_self":payload["delta_self"],"delta_margin":payload["delta_margin"],
  "baseline_flow":b["post_land_flow"],"candidate_flow":c["post_land_flow"],
  "baseline_plant":b["post_land_plant"],"candidate_plant":c["post_land_plant"],
},ensure_ascii=False,separators=(",",":")))
