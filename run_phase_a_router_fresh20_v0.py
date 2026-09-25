#!/usr/bin/env python3
"""Fresh20 Battle: Active WR-02 vs WR-02 + Phase A Router v0."""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active
import phase_a_router_v0 as router

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_router_fresh20_v0_{SEED}_seat{SEAT}.json")


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
    baseline=play(active)
    candidate=play(router)
    payload={
      "schema":"kaggriculture.phase-a-router.fresh20.v0",
      "seed":SEED,"seat":SEAT,
      "active_wr02":baseline,
      "router":candidate,
      "paired_delta":{
        "self":candidate["terminal"]["self"]-baseline["terminal"]["self"],
        "margin":candidate["terminal"]["margin"]-baseline["terminal"]["margin"],
      },
      "boundary":[
        "Current Active Model is WR-02.",
        "Router uses only self-visible outer State at the first observed turn of each day.",
        "Router choices are HOLD / Surface / Throughput / Engine.",
        "No opponent state, seed, terminal reward, future state, or hidden model trace is routing input.",
        "Primary adoption criterion is terminal self.",
        "Every comparison records baseline absolute mean self, candidate absolute mean self, and delta."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE_A_ROUTER_FRESH20 "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "active":baseline["terminal"],
      "router":candidate["terminal"],
      "delta":payload["paired_delta"],
      "mode_days":candidate["telemetry"].get("mode_days",{})
    },ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
