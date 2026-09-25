#!/usr/bin/env python3
"""Fresh20 Battle: Active WR-02 vs Phase A Growth Cycle v0."""
import json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as active
import phase_a_growth_cycle_v0 as cycle

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"phase_a_growth_cycle_fresh20_v0_{SEED}_seat{SEAT}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"


def play(module):
    configure();module.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT];players[SEAT]=module.agent
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
    b=play(active);c=play(cycle)
    payload={
      "schema":"kaggriculture.phase-a-growth-cycle.fresh20.v0",
      "seed":SEED,"seat":SEAT,
      "active_wr02":b,"cycle":c,
      "paired_delta":{
        "self":c["terminal"]["self"]-b["terminal"]["self"],
        "margin":c["terminal"]["margin"]-b["terminal"]["margin"],
      },
      "boundary":[
        "Current Active Model WR-02 is the paired baseline.",
        "Growth Cycle composes Engine -> Throughput -> Surface using observable transformation boundaries only.",
        "No opponent state, seed, terminal reward, future state, or hidden model trace drives stage transitions.",
        "Primary adoption criterion is terminal self.",
        "Record baseline absolute mean self, candidate absolute mean self, and delta."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE_A_GROWTH_CYCLE "+json.dumps({
      "seed":SEED,"seat":SEAT,
      "active":b["terminal"],"cycle":c["terminal"],"delta":payload["paired_delta"],
      "stage_turns":c["telemetry"].get("stage_turns",{}),
      "transition_count":len(c["telemetry"].get("transitions",[]))
    },ensure_ascii=False,separators=(",",":")))
if __name__=="__main__":main()
