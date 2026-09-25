#!/usr/bin/env python3
"""Fresh20 paired Battle: current WR-02 vs WR-02 + native Origin hysteresis."""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_native_origin_hysteresis_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"wr02_native_origin_hysteresis_fresh20_v0_{SEED}_seat{SEAT}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def play(module):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = module.agent
    env.run(players)
    rewards = [float(x.reward) for x in env.state]
    return {
        "self": rewards[SEAT],
        "opponent": rewards[1 - SEAT],
        "margin": rewards[SEAT] - rewards[1 - SEAT],
        "telemetry": module.get_telemetry(),
    }


def main():
    b = play(current)
    c = play(candidate)
    payload = {
        "schema": "kaggriculture.wr02-native-origin-hysteresis.fresh20.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": b,
        "candidate": c,
        "delta_self": c["self"] - b["self"],
        "delta_margin": c["margin"] - b["margin"],
        "boundary": [
            "Primary comparison is current Active Model WR-02 versus WR-02 plus one-turn native Origin switch hysteresis.",
            "Only Current's own native Origin mode continuity is changed.",
            "ENDGAME remains immediate at the existing finite-horizon boundary.",
            "No external role, teacher label, opponent policy copy, fixed sequence, or target rewrite is introduced.",
            "Terminal self is the adoption authority."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("WR02_NATIVE_HYSTERESIS_FRESH20 " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "current_self": b["self"],
        "candidate_self": c["self"],
        "delta_self": payload["delta_self"],
        "delta_margin": payload["delta_margin"],
        "delayed_switch_turns": c["telemetry"].get("delayed_switch_turns", 0),
        "confirmed_switches": c["telemetry"].get("confirmed_switches", 0),
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
