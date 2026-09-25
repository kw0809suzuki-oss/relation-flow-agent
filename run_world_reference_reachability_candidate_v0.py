#!/usr/bin/env python3
"""World Reference Reachability Candidate v0 — fixed five Battle A/B."""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import world_reference_reachability_candidate_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"world_reference_reachability_candidate_v0_{SEED}_seat{SEAT}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def play(agent_fn,reset_fn,get_tel=None):
    configure()
    reset_fn()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=agent_fn
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    out={
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        }
    }
    if get_tel is not None:
        out["telemetry"]=get_tel()
    return out


def main():
    b=play(baseline.agent,baseline.reset_telemetry,baseline.get_telemetry)
    c=play(candidate.agent,candidate.reset_telemetry,candidate.get_telemetry)
    tel=c["telemetry"]
    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-reachability-candidate.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":b,
        "candidate":c,
        "terminal_delta":{
            "self":c["terminal"]["self"]-b["terminal"]["self"],
            "opponent":c["terminal"]["opponent"]-b["terminal"]["opponent"],
            "margin":c["terminal"]["margin"]-b["terminal"]["margin"],
        },
        "connection_telemetry":{
            "reopened_orders":tel.get("reopened_orders",0),
            "removed_orders":tel.get("removed_orders",0),
            "reopened_by_key":tel.get("reopened_by_key",{}),
            "removed_by_key":tel.get("removed_by_key",{}),
            "events":tel.get("events",[]),
        },
        "boundary":[
            "Baseline is unchanged strong_origin_v2_body_only_v0.",
            "Candidate changes only the Day14+ closure boundary for native BUY_SEED / BUY_ANIMAL orders.",
            "A native productive purchase is retained only when its public first-output schedule can reach the season terminal.",
            "The candidate does not select crop/animal type or quantity and does not add a new purchase not already proposed by the native model.",
            "BUY_LAND and BUY_PRODUCT COW remain under the adopted Day14 closure.",
            "Terminal self is the adoption criterion. Local reopening is not evidence of improvement."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WORLD_REFERENCE_REACHABILITY_CANDIDATE "+json.dumps({
        "seed":SEED,
        "seat":SEAT,
        "baseline":b["terminal"],
        "candidate":c["terminal"],
        "delta":payload["terminal_delta"],
        "reopened_orders":payload["connection_telemetry"]["reopened_orders"],
        "reopened_by_key":payload["connection_telemetry"]["reopened_by_key"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
