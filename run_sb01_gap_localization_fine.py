#!/usr/bin/env python3
"""Fine-grained observation-only replay for SB-01 gap localization.

No strategy or candidate behavior is changed.
Records first observations on Day 6/8/10/12 to localize the earliest
large expansion of the remaining strength gap.
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
TARGET_DAYS = (6, 8, 10, 12)
OUT = Path(f"sb01_gap_fine_{SEED}.json")

OUTPUT_ITEMS = ("MILK", "WOOL", "EGG", "FERTILIZER")
TRACKED_STOCK_ITEMS = ("WHEAT", "COW", "MILK", "WOOL", "EGG", "FERTILIZER")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def _private_total(private, item):
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []
    return int(shed.get(item, 0) or 0) + sum(int((inv or {}).get(item, 0) or 0) for inv in inventories)


def _public_assets(farm):
    active_tiles = 0
    crops = {}
    animals = {}
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
        "production_asset_count": sum(crops.values()) + sum(animals.values()),
    }


def snapshot(obs):
    player = int(obs["player"])
    me = obs["farms"][player]
    opp = obs["farms"][1-player]
    private = obs.get("private", {}) or {}
    stock = {item: _private_total(private, item) for item in TRACKED_STOCK_ITEMS}
    sellable = {item: stock[item] for item in OUTPUT_ITEMS}

    self_money = float(me.get("money", 0) or 0)
    opponent_money = float(opp.get("money", 0) or 0)
    return {
        "day": int(obs.get("day", 0) or 0),
        "self_money": self_money,
        "opponent_money": opponent_money,
        "money_margin": self_money - opponent_money,
        "self_public_assets": _public_assets(me),
        "opponent_public_assets": _public_assets(opp),
        "self_stock": stock,
        "self_sellable_outputs": sellable,
        "self_sellable_output_total": sum(sellable.values()),
        "opponent_stock": "unavailable_private_state",
        "opponent_sellable_outputs": "unavailable_private_state",
    }


def main():
    configure()
    snapshots = {}
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]

    def observed(obs):
        day = int(obs.get("day", 0) or 0)
        if day in TARGET_DAYS and str(day) not in snapshots:
            snapshots[str(day)] = snapshot(obs)
        return combat.agent(obs)

    players[SEAT] = observed
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    payload = {
        "schema": "kaggriculture.sb01.remaining-strength-gap-localization.fine.v0",
        "probe": "Remaining Strength Gap Localization Fine",
        "mode": "observation_only_replay",
        "seed": SEED,
        "seat": SEAT,
        "benchmark": "strength_benchmark_v0",
        "snapshot": "SB-01",
        "snapshots": snapshots,
        "terminal_result": {
            "self": rewards[SEAT],
            "opponent": rewards[1-SEAT],
            "margin": rewards[SEAT] - rewards[1-SEAT],
        },
        "boundary": [
            "No strategy action, rule, threshold, or candidate is changed.",
            "Uses the exact fixed SB-01 seed/seat/opponent/runtime configuration.",
            "Only Day 6/8/10/12 first-observation snapshots are added.",
            "Opponent private stock is unavailable and is not inferred.",
            "This probe localizes the first large gap expansion; it does not identify cause."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SB01_GAP_FINE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
