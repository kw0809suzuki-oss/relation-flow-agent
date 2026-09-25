#!/usr/bin/env python3
"""Fresh20 paired Battle: current WR-02 vs WR-02 + P12 Day0 reservation."""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_p12_day0_reservation_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"wr02_p12_day0_reservation_fresh20_v0_{SEED}_seat{SEAT}.json")


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
    }


def main():
    b = play(current)
    c = play(candidate)
    payload = {
        "schema": "kaggriculture.wr02-p12-day0-reservation.fresh20.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": b,
        "candidate": c,
        "delta_self": c["self"] - b["self"],
        "delta_margin": c["margin"] - b["margin"],
        "boundary": [
            "Primary comparison is current Active Model WR-02 versus WR-02 plus existing P12 Day0 target reservation.",
            "Only the existing Day0 Strong Origin work-target reservation is added.",
            "Day1 onward uses the same Current F; WR-02 Day14+ behavior is unchanged.",
            "No Seyamalam action, teacher label, external role, field abstraction, or fixed sequence is injected.",
            "Terminal self is the adoption authority."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("WR02_P12_FRESH20 " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
