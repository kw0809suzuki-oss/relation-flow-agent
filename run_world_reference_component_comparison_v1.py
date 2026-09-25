#!/usr/bin/env python3
"""WR-01 / WR-02 / Bundle fixed-five comparison v1."""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as baseline
import world_reference_reachability_candidate_v0 as wr01
import wr02_same_tile_plant_deconfliction_v0 as wr02
import world_reference_bundle_wr01_wr02_v0 as bundle

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"world_reference_component_comparison_v1_{SEED}_seat{SEAT}.json")


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
    arms={
        "baseline":play(baseline),
        "wr01":play(wr01),
        "wr02":play(wr02),
        "bundle":play(bundle),
    }
    b=arms["baseline"]["terminal"]
    payload={
        "schema":"kaggriculture.strong-origin-v2.world-reference-component-comparison.v1",
        "seed":SEED,
        "seat":SEAT,
        **arms,
        "delta_self":{
            k:v["terminal"]["self"]-b["self"]
            for k,v in arms.items() if k!="baseline"
        },
        "delta_margin":{
            k:v["terminal"]["margin"]-b["margin"]
            for k,v in arms.items() if k!="baseline"
        },
        "connection":{
            "wr01_reopened_orders":arms["wr01"]["telemetry"].get("reopened_orders",0),
            "wr02_duplicate_seen":arms["wr02"]["telemetry"].get("duplicate_plant_commands_seen",0),
            "wr02_moved":arms["wr02"]["telemetry"].get("deconflicted_to_move",0),
            "wr02_passed":arms["wr02"]["telemetry"].get("deconflicted_to_pass",0),
            "bundle_wr01_reopened_orders":arms["bundle"]["telemetry"].get("wr01",{}).get("reopened_orders",0),
            "bundle_wr02_duplicate_seen":arms["bundle"]["telemetry"].get("wr02",{}).get("duplicate_plant_commands_seen",0),
            "bundle_wr02_moved":arms["bundle"]["telemetry"].get("wr02",{}).get("deconflicted_to_move",0),
            "bundle_wr02_passed":arms["bundle"]["telemetry"].get("wr02",{}).get("deconflicted_to_pass",0),
        },
        "boundary":[
            "All four arms use identical seed/seat/opponent.",
            "WR-02 changes only same-tile duplicate PLANT actions from Day14 onward.",
            "WR-02 does not choose crop type, market order, quantity, or timing of non-duplicate PLANT actions.",
            "Bundle applies unchanged WR-01 first, then WR-02 action deconfliction.",
            "Terminal self is the primary comparison target."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WR_COMPONENT_COMPARISON_V1 "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "terminals":{k:v["terminal"] for k,v in arms.items()},
        "delta_self":payload["delta_self"],
        "connection":payload["connection"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
