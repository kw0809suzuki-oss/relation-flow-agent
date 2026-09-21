#!/usr/bin/env python3
"""Observation-only asset-category decomposition for SB-01 Day 6 -> Day 8.

No strategy/candidate behavior is changed.
Captures public asset categories at first observation on Day 6 and Day 8.
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
TARGET_DAYS = (6, 8)
OUT = Path(f"sb01_asset_split_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def _public_assets(farm):
    crops = {}
    animals = {}
    active_tiles = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile == "LOCKED" or tile is None:
                continue
            active_tiles += 1
            if not isinstance(tile, dict):
                continue
            crop = tile.get("crop")
            animal = tile.get("animal")
            if crop:
                crops[crop] = crops.get(crop, 0) + 1
            if animal:
                animals[animal] = animals.get(animal, 0) + 1

    return {
        "active_tiles": active_tiles,
        "hands": len(farm.get("hands", []) or []),
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", []) or []),
        "crops": crops,
        "animals": animals,
        "crop_total": sum(crops.values()),
        "animal_total": sum(animals.values()),
        "production_asset_count": sum(crops.values()) + sum(animals.values()),
    }


def snapshot(obs):
    p = int(obs["player"])
    me = obs["farms"][p]
    opp = obs["farms"][1-p]
    return {
        "day": int(obs.get("day", 0) or 0),
        "self_money": float(me.get("money", 0) or 0),
        "opponent_money": float(opp.get("money", 0) or 0),
        "self_public_assets": _public_assets(me),
        "opponent_public_assets": _public_assets(opp),
    }


def main():
    configure()
    snaps = {}
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]

    def observed(obs):
        day = int(obs.get("day", 0) or 0)
        if day in TARGET_DAYS and str(day) not in snaps:
            snaps[str(day)] = snapshot(obs)
        return combat.agent(obs)

    players[SEAT] = observed
    env.run(players)

    payload = {
        "schema": "kaggriculture.sb01.asset-category-split.v0",
        "probe": "Remaining Strength Gap Asset Category Split",
        "mode": "observation_only_replay",
        "seed": SEED,
        "seat": SEAT,
        "snapshot": "SB-01",
        "snapshots": snaps,
        "boundary": [
            "No strategy, rule, threshold, or candidate is changed.",
            "Uses exact SB-01 fixed seed/seat/opponent/runtime conditions.",
            "Only public asset categories on Day 6 and Day 8 are observed.",
            "This probe identifies where category separation appears; it does not identify cause."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SB01_ASSET_SPLIT_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
