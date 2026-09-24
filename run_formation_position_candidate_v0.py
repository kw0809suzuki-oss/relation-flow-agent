#!/usr/bin/env python3
"""Formation Position Candidate v0 — fixed five-Battle A/B runner."""
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import formation_position_candidate_v0 as candidate
import run_asset_formation_map_v0 as af

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"formation_position_candidate_v0_{SEED}_seat{SEAT}.json")

def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"

def local_view(obs):
    p=int(obs["player"])
    farm=obs["farms"][p]
    instances=[]
    day=int(obs.get("day",0) or 0)
    for y,row in enumerate(farm.get("tiles",[]) or []):
        for x,tile in enumerate(row or []):
            z=af.asset_instance(tile,x,y,day)
            if z is not None:
                instances.append(z)
    s=af.summarize(instances)

    positions=[tuple(farm.get("farmer",()))]
    positions += [tuple(x) for x in (farm.get("hands",[]) or [])]
    units_on_empty=0
    for pos in positions:
        if len(pos)<2: continue
        x,y=int(pos[0]),int(pos[1])
        rows=farm.get("tiles",[]) or []
        if 0<=y<len(rows) and 0<=x<len(rows[y]) and rows[y][x] is None:
            units_on_empty += 1

    return {
        "money":float(farm.get("money",0) or 0),
        "hands_count":len(farm.get("hands",[]) or []),
        "units_on_empty_tile_count":units_on_empty,
        "productive_occupied_tile_count":af.land_context(farm)["productive_occupied_tile_count"],
        "present_asset_count":{
            typ:int(v["present_asset_count"]) for typ,v in s.items()
        },
    }

def play(agent_fn, reset_fn):
    configure()
    reset_fn()
    views={}
    def observed(obs):
        day=int(obs.get("day",0) or 0)
        hour=int(obs.get("hour",0) or 0)
        if day==0 and hour in (12,13,14,15):
            views[f"h{hour}"]=local_view(af.plain(obs))
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
    payload={
        "schema":"kaggriculture.strong-origin-v2.formation-position-candidate.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":b,
        "candidate":c,
        "candidate_telemetry":candidate.get_telemetry(),
        "terminal_delta":{
            "self":c["terminal"]["self"]-b["terminal"]["self"],
            "opponent":c["terminal"]["opponent"]-b["terminal"]["opponent"],
            "margin":c["terminal"]["margin"]-b["terminal"]["margin"],
        },
        "boundary":[
            "Candidate changes only Day0 h12 unit movement, up to three units, toward distinct adjacent empty tiles.",
            "Market orders are unchanged by the wrapper.",
            "No crop or animal composition is forced.",
            "From h13 onward Body-only behavior is native.",
            "Adoption is not decided locally; terminal self remains the Battle criterion."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FORMATION_POSITION_CANDIDATE "+json.dumps({
        "seed":SEED,
        "seat":SEAT,
        "baseline":b["terminal"],
        "candidate":c["terminal"],
        "delta":payload["terminal_delta"],
        "candidate_telemetry":{
            "modified_turns":payload["candidate_telemetry"].get("modified_turns",0),
            "modified_unit_actions":payload["candidate_telemetry"].get("modified_unit_actions",0),
            "targets":payload["candidate_telemetry"].get("targets",[]),
        },
        "baseline_h13":b["views"].get("h13"),
        "candidate_h13":c["views"].get("h13"),
        "baseline_h14":b["views"].get("h14"),
        "candidate_h14":c["views"].get("h14"),
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
