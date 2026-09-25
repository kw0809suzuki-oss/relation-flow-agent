#!/usr/bin/env python3
"""Fresh20 Battle for three Phase A takeoff patterns against Active WR-02."""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active
import phase_a_takeoff_variants_v0 as variants

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_takeoff_fresh20_v0_{SEED}_seat{SEAT}.json")
MODES=("surface_first","throughput_first","engine_first")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def play_active():
    configure();active.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=active.agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "telemetry":active.get_telemetry(),
    }


def play_mode(mode):
    configure();variants.set_mode(mode);variants.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=variants.agent
    env.run(players)
    rewards=[float(x.reward) for x in env.state]
    return {
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT]},
      "telemetry":variants.get_telemetry(),
    }


def main():
    active_result=play_active()
    candidates={m:play_mode(m) for m in MODES}
    payload={
      "schema":"kaggriculture.phase-a-takeoff.fresh20.v0",
      "seed":SEED,"seat":SEAT,
      "active_wr02":active_result,
      "candidates":candidates,
      "paired_delta":{
        m:{
          "self":candidates[m]["terminal"]["self"]-active_result["terminal"]["self"],
          "margin":candidates[m]["terminal"]["margin"]-active_result["terminal"]["margin"],
        } for m in MODES
      },
      "boundary":[
        "All four arms use the same seed and seat.",
        "Active reference is Baseline + WR-02.",
        "Surface First changes only early LAND timing.",
        "Throughput First changes only early HIRE timing.",
        "Engine First strengthens early native productive commitment without inventing a crop outside the native target mix.",
        "All variants stop Phase A intervention at Day12 and preserve D14 closure.",
        "Adoption is decided only by terminal self."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE_A_TAKEOFF_FRESH20 "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "active":active_result["terminal"],
      "candidates":{m:candidates[m]["terminal"] for m in MODES},
      "delta":payload["paired_delta"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
