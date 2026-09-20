#!/usr/bin/env python3
"""Open Learning Probe batch v0.

Two fresh unknown Battles. The existing taxonomy is reference-only and no
candidate, including temporal_realization, is pre-seeded into the answer space.
"""
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state
from open_learning_probe_v0 import build_open_learning_packet

CASES=[(6202,1),(6203,0)]
OPPONENT=base.OPPONENT
OPPONENT_LABEL="Seyamalam v21"
OUT=Path("open_learning_probe_batch_v0.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(seed,seat):
    configure()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    daily=[]
    last_day=None
    def agent(obs):
        nonlocal last_day
        day=int(obs.get("day",0) or 0)
        s=observe_state(obs)
        if day!=last_day:
            daily.append(s); last_day=day
        else:
            daily[-1]=s
        return combat.agent(obs)
    players=[OPPONENT,OPPONENT]
    players[seat]=agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    battle={
        "case_identity":{
            "seed":seed,"seat":seat,"opponent":OPPONENT_LABEL,
            "previous_learning_label":None,
            "purpose":"fresh unknown-case open learning observation",
        },
        "terminal":{
            "self":rewards[seat],"opponent":rewards[1-seat],
            "margin":rewards[seat]-rewards[1-seat],
            "win_loss":"win" if rewards[seat]>rewards[1-seat] else "loss" if rewards[seat]<rewards[1-seat] else "draw",
        },
        "daily_observed_state":daily,
        "run_id":os.environ.get("GITHUB_RUN_ID"),
    }
    return build_open_learning_packet(battle)

def compact(packet):
    b=packet["battle"]
    ds=b["daily_observed_state"]
    return {
        "case":b["case_identity"],
        "terminal":b["terminal"],
        "daily_observations":len(ds),
        "closing_days":[{
            "day":s["time"]["day"],
            "remaining":s["time"]["remaining_days"],
            "self_money":s["money"]["self"],
            "opp_money":s["money"]["opponent"],
            "hands":s["capacity"]["hands"],
            "cows":s["capacity"]["cows"],
            "planted":s["capacity"]["planted_tiles"],
            "harvestable":s["flow_outputs"]["harvestable_tiles"],
            "seed_wheat":s["flow_inputs"]["seed_inventory"]["WHEAT"],
            "weeds":s["work_state"]["weeds"],
        } for s in ds],
        "boundary":packet["learning_boundary"],
        "taxonomy":packet["reference_taxonomy"],
    }

def main():
    packets=[play(seed,seat) for seed,seat in CASES]
    payload={
        "schema":"kaggriculture.open-learning-probe-batch.v0",
        "cases":packets,
        "boundary":[
            "Fresh cases are not labeled before observation.",
            "Existing taxonomy is reference-only.",
            "temporal_realization is not supplied as an answer label.",
            "No learning or taxonomy extension is auto-adopted.",
        ],
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for p in packets:
        print("OPEN_LEARNING_BATCH_CASE "+json.dumps(compact(p),ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
