#!/usr/bin/env python3
"""Composition Transformation Candidate v0 — fixed five-Battle A/B."""
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import composition_transformation_candidate_v0 as candidate
import run_asset_formation_map_v0 as af

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"composition_transformation_candidate_v0_{SEED}_seat{SEAT}.json")

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"

def local_view(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    day=int(obs.get("day",0) or 0)
    instances=[]
    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,tile in enumerate(row or []):
            z=af.asset_instance(tile,x,y,day)
            if z is not None:
                instances.append(z)
    s=af.summarize(instances)
    return {
        "money":float(farm.get("money",0) or 0),
        "present_asset_count":{
            typ:int(v["present_asset_count"]) for typ,v in s.items()
        },
        "current_harvestable_units":{
            typ:int(v["current_harvestable_units"]) for typ,v in s.items()
        },
        "near4_conditional":{
            typ:int(v["near_window_base_units_conditional"]) for typ,v in s.items()
        },
    }

def play(agent_fn, reset_fn):
    configure()
    reset_fn()
    views={}
    def observed(obs):
        day=int(obs.get("day",0) or 0)
        hour=int(obs.get("hour",0) or 0)
        if (day==0 and hour in (14,15,23)) or (day in (2,8,10,12,16,20) and hour==0):
            views[f"d{day}_h{hour}"]=local_view(af.plain(obs))
        return agent_fn(obs)

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=observed
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "views":views,
    }

def main():
    b=play(baseline.agent,baseline.reset_telemetry)
    c=play(candidate.agent,candidate.reset_telemetry)
    tel=candidate.get_telemetry()
    payload={
        "schema":"kaggriculture.strong-origin-v2.composition-transformation-candidate.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":b,
        "candidate":c,
        "candidate_telemetry":{
            "modified_turns":tel.get("modified_turns",0),
            "replaced_actions":tel.get("replaced_actions",0),
            "replacement":tel.get("replacement"),
        },
        "terminal_delta":{
            "self":c["terminal"]["self"]-b["terminal"]["self"],
            "opponent":c["terminal"]["opponent"]-b["terminal"]["opponent"],
            "margin":c["terminal"]["margin"]-b["terminal"]["margin"],
        },
        "boundary":[
            "Candidate changes exactly one native Day0 h14 PLANT WHEAT into PLANT MELON when MELON seed stock exists.",
            "Unit, tile, timing, action count, movement, and market orders are not otherwise changed.",
            "All behavior after the single replacement remains native Body-only.",
            "Local Asset State checkpoints are retained only to verify transformation and downstream persistence.",
            "Adoption is determined by terminal self, not local Asset composition."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMPOSITION_TRANSFORMATION_CANDIDATE "+json.dumps({
        "seed":SEED,
        "seat":SEAT,
        "baseline":b["terminal"],
        "candidate":c["terminal"],
        "delta":payload["terminal_delta"],
        "telemetry":payload["candidate_telemetry"],
        "baseline_h15":b["views"].get("d0_h15"),
        "candidate_h15":c["views"].get("d0_h15"),
        "baseline_d10":b["views"].get("d10_h0"),
        "candidate_d10":c["views"].get("d10_h0"),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
