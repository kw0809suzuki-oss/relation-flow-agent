#!/usr/bin/env python3
"""WR component comparison v0: baseline / WR-01 / WR-02 / bundle."""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import world_reference_reachability_candidate_v0 as wr01
import world_reference_productive_deficit_land_candidate_v0 as wr02
import world_reference_bundle_v0 as bundle

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"world_reference_component_comparison_v0_{SEED}_seat{SEAT}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def play(module):
    configure()
    module.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=module.agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "telemetry":module.get_telemetry(),
    }


def main():
    b=play(baseline)
    a=play(wr01)
    l=play(wr02)
    u=play(bundle)
    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-component-comparison.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":b,
        "wr01":a,
        "wr02":l,
        "bundle":u,
        "delta_self":{
            "wr01":a["terminal"]["self"]-b["terminal"]["self"],
            "wr02":l["terminal"]["self"]-b["terminal"]["self"],
            "bundle":u["terminal"]["self"]-b["terminal"]["self"],
        },
        "delta_margin":{
            "wr01":a["terminal"]["margin"]-b["terminal"]["margin"],
            "wr02":l["terminal"]["margin"]-b["terminal"]["margin"],
            "bundle":u["terminal"]["margin"]-b["terminal"]["margin"],
        },
        "connection":{
            "wr01_reopened_orders":a["telemetry"].get("reopened_orders",0),
            "wr02_reopened_land_orders":l["telemetry"].get("reopened_land_orders",0),
            "wr02_events":l["telemetry"].get("events",[]),
            "bundle_wr01_reopened_orders":u["telemetry"].get("wr01_reopened_orders",0),
            "bundle_wr02_reopened_land_orders":u["telemetry"].get("wr02_reopened_land_orders",0),
        },
        "boundary":[
            "All four arms use the same seed/seat and unchanged opponent.",
            "WR-01 and WR-02 are independent components; bundle applies both rules.",
            "WR-02 never creates BUY_LAND: it only retains a native Day14+ BUY_LAND when public committed-production residual is opponent-positive.",
            "Terminal self is the primary comparison target."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WR_COMPONENT_COMPARISON "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "baseline":b["terminal"],
        "wr01":a["terminal"],
        "wr02":l["terminal"],
        "bundle":u["terminal"],
        "delta_self":payload["delta_self"],
        "connection":{
            "wr01":payload["connection"]["wr01_reopened_orders"],
            "wr02_land":payload["connection"]["wr02_reopened_land_orders"],
            "bundle_wr01":payload["connection"]["bundle_wr01_reopened_orders"],
            "bundle_wr02_land":payload["connection"]["bundle_wr02_reopened_land_orders"],
        }
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
