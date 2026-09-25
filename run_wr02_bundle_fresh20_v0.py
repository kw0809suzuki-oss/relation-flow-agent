#!/usr/bin/env python3
"""Fresh20 continuation: run WR-02 and WR-01+WR-02 bundle only."""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as wr02
import world_reference_bundle_wr01_wr02_v0 as bundle

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"wr02_bundle_fresh20_v0_{SEED}_seat{SEAT}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def play(module):
    configure();module.reset_telemetry()
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
    w2=play(wr02); b=play(bundle)
    payload={
        "schema":"kaggriculture.strong-origin-v2.wr02-bundle-fresh20.v0",
        "seed":SEED,"seat":SEAT,
        "wr02":w2,
        "bundle":b,
        "connection":{
            "wr02_duplicate_seen":w2["telemetry"].get("duplicate_plant_commands_seen",0),
            "wr02_moved":w2["telemetry"].get("deconflicted_to_move",0),
            "bundle_wr01_reopened_orders":b["telemetry"].get("wr01",{}).get("reopened_orders",0),
            "bundle_wr02_duplicate_seen":b["telemetry"].get("wr02",{}).get("duplicate_plant_commands_seen",0),
            "bundle_wr02_moved":b["telemetry"].get("wr02",{}).get("deconflicted_to_move",0),
        },
        "boundary":[
            "Uses the same independent seeds 8201-8220 and alternating seats as WR-01 fresh20.",
            "WR-02 and Bundle are unchanged from the fixed-five comparison.",
            "Baseline and standalone WR-01 are reused only from the existing matched fresh20 result for aggregation."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WR02_BUNDLE_FRESH20 "+json.dumps({
        "seed":SEED,"seat":SEAT,
        "wr02":w2["terminal"],
        "bundle":b["terminal"],
        "connection":payload["connection"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
