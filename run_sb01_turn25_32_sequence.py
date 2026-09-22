#!/usr/bin/env python3
"""Observation-only sequence probe for SB-01 Day 7 turns 25-32.

No strategy/candidate behavior is changed.
Captures every self observation in the short window around the opponent
quadrant expansion and first production-asset increase.
"""
import json
import os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
OUT = Path(f"sb01_turn25_32_sequence_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def pub(farm):
    crops, animals = {}, {}
    active_tiles = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile == "LOCKED" or tile is None:
                continue
            active_tiles += 1
            if isinstance(tile, dict):
                c = tile.get("crop")
                a = tile.get("animal")
                if c:
                    crops[c] = crops.get(c, 0) + 1
                if a:
                    animals[a] = animals.get(a, 0) + 1
    return {
        "active_tiles": active_tiles,
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", []) or []),
        "hands": len(farm.get("hands", []) or []),
        "crops": crops,
        "crop_total": sum(crops.values()),
        "animals": animals,
        "animal_total": sum(animals.values()),
        "production_asset_count": sum(crops.values()) + sum(animals.values()),
    }


def main():
    configure()
    seq = []
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]

    def observed(obs):
        day = int(obs.get("day", 0) or 0)
        turn = int(obs.get("turn", 0) or 0)
        if day == 7 and 25 <= turn <= 32:
            p = int(obs["player"])
            me = obs["farms"][p]
            op = obs["farms"][1-p]
            sm = float(me.get("money", 0) or 0)
            om = float(op.get("money", 0) or 0)
            seq.append({
                "turn": turn,
                "self_money": sm,
                "opponent_money": om,
                "money_margin": sm - om,
                "self_public": pub(me),
                "opponent_public": pub(op),
            })
        return combat.agent(obs)

    players[SEAT] = observed
    env.run(players)

    payload = {
        "schema": "kaggriculture.sb01.turn25-32-sequence.v0",
        "probe": "Remaining Strength Gap Turn25-32 Sequence",
        "mode": "observation_only_replay",
        "seed": SEED,
        "seat": SEAT,
        "snapshot": "SB-01",
        "sequence": seq,
        "boundary": [
            "No strategy, rule, threshold, or candidate is changed.",
            "Uses exact fixed SB-01 seed/seat/opponent/runtime conditions.",
            "Only public state from Day 7 turns 25 through 32 is recorded.",
            "This probe localizes sequence structure and does not establish cause."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SB01_TURN25_32_SEQUENCE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
