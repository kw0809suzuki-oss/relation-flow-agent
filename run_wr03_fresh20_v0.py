#!/usr/bin/env python3
"""Fresh20 paired Battle: Body / WR-02 / WR-03 / WR-02+WR-03."""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body
import wr02_same_tile_plant_deconfliction_v0 as wr02
import wr03_cycle_carry_reserve_release_v0 as wr03
import world_reference_bundle_wr02_wr03_v0 as bundle

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"wr03_fresh20_v0_{SEED}_seat{SEAT}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def play(module):
    configure(); module.reset_telemetry()
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
    results={
      "body":play(body),
      "wr02":play(wr02),
      "wr03":play(wr03),
      "bundle":play(bundle),
    }
    payload={
      "schema":"kaggriculture.wr03.fresh20.v0",
      "seed":SEED,"seat":SEAT,
      "results":results,
      "paired_delta":{
        "wr02_vs_body":results["wr02"]["terminal"]["self"]-results["body"]["terminal"]["self"],
        "wr03_vs_body":results["wr03"]["terminal"]["self"]-results["body"]["terminal"]["self"],
        "bundle_vs_body":results["bundle"]["terminal"]["self"]-results["body"]["terminal"]["self"],
        "bundle_vs_wr02":results["bundle"]["terminal"]["self"]-results["wr02"]["terminal"]["self"],
        "bundle_vs_wr03":results["bundle"]["terminal"]["self"]-results["wr03"]["terminal"]["self"],
      },
      "boundary":[
        "Fresh independent seeds 8301-8320 with alternating seats.",
        "Body-only, WR-02, WR-03, and WR-02+WR-03 use identical seed/seat per case.",
        "Primary adoption comparison is current Active Model WR-02 versus WR-02+WR-03.",
        "WR-03 changes only the native reserve_base gate while a generated-Return cycle is open.",
        "WR-03 does not prescribe LAND, crop, animal, seed, hire, position, or quantity.",
        "D14 closure remains active in all arms."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("WR03_FRESH20 "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "terminal":{k:v["terminal"] for k,v in results.items()},
      "delta":payload["paired_delta"],
      "wr03":{"signals":results["wr03"]["telemetry"].get("wr03_return_signals",0),
              "active_turns":results["wr03"]["telemetry"].get("wr03_active_turns",0),
              "surface_closures":results["wr03"]["telemetry"].get("wr03_surface_closures",0)}
    },ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
