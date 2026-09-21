#!/usr/bin/env python3
"""Observation-only replay of the fixed SB-01 Strength Benchmark set.

No strategy or candidate behavior is changed.
The worker replays one fixed SB-01 case and records only representative
observable state snapshots for Remaining Strength Gap Localization.

Snapshots:
- first observation on Day 4
- first observation on Day 12
- first observation on Day 20
- last observation before terminal + terminal rewards

Opponent private inventory is not observable and remains unavailable.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
TARGET_DAYS = (4, 12, 20)
OUT = Path(f"sb01_gap_localization_{SEED}.json")

OUTPUT_ITEMS = ("MILK", "WOOL", "EGG", "FERTILIZER")
TRACKED_STOCK_ITEMS = ("WHEAT", "COW", "MILK", "WOOL", "EGG", "FERTILIZER")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    # Exact SB-01 benchmark runtime configuration.
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


def snapshot(obs, label):
    player = int(obs["player"])
    me = obs["farms"][player]
    opp = obs["farms"][1 - player]
    private = obs.get("private", {}) or {}

    stock = {item: _private_total(private, item) for item in TRACKED_STOCK_ITEMS}
    sellable_outputs = {item: stock[item] for item in OUTPUT_ITEMS}

    self_money = float(me.get("money", 0) or 0)
    opp_money = float(opp.get("money", 0) or 0)

    return {
        "label": label,
        "day": int(obs.get("day", 0) or 0),
        "self_money": self_money,
        "opponent_money": opp_money,
        "money_margin": self_money - opp_money,
        "self_public_assets": _public_assets(me),
        "opponent_public_assets": _public_assets(opp),
        "self_stock": stock,
        "self_sellable_outputs": sellable_outputs,
        "self_sellable_output_total": sum(sellable_outputs.values()),
        "opponent_stock": "unavailable_private_state",
        "opponent_sellable_outputs": "unavailable_private_state",
    }


def play():
    configure()
    snapshots = {}
    last_obs = None

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]

    def observed(obs):
        nonlocal last_obs
        last_obs = copy.deepcopy(obs)
        day = int(obs.get("day", 0) or 0)
        if day in TARGET_DAYS and str(day) not in snapshots:
            snapshots[str(day)] = snapshot(obs, f"day_{day}_first_observation")
        return combat.agent(obs)

    players[SEAT] = observed
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    terminal_self = rewards[SEAT]
    terminal_opponent = rewards[1-SEAT]
    terminal_margin = terminal_self - terminal_opponent

    terminal_state = None
    if last_obs is not None:
        terminal_state = snapshot(last_obs, "last_observation_before_terminal")
        terminal_state["terminal_reward_self"] = terminal_self
        terminal_state["terminal_reward_opponent"] = terminal_opponent
        terminal_state["terminal_reward_margin"] = terminal_margin

    return {
        "snapshots": snapshots,
        "terminal": terminal_state,
        "terminal_result": {
            "self": terminal_self,
            "opponent": terminal_opponent,
            "margin": terminal_margin,
            "outcome": "win" if terminal_margin > 0 else "loss" if terminal_margin < 0 else "draw",
        },
    }


def main():
    result = play()
    payload = {
        "schema": "kaggriculture.sb01.remaining-strength-gap-localization.v0",
        "probe": "Remaining Strength Gap Localization",
        "mode": "observation_only_replay",
        "seed": SEED,
        "seat": SEAT,
        "benchmark": "strength_benchmark_v0",
        "snapshot": "SB-01",
        "commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        **result,
        "boundary": [
            "No strategy action, rule, threshold, or candidate is changed by this probe.",
            "Replay uses the exact fixed SB-01 seed and seat set and the same benchmark runtime configuration.",
            "Day 4/12/20 snapshots are the first observation seen on each target day.",
            "Terminal state is the last observation seen before terminal; terminal rewards are recorded separately.",
            "Opponent private stock and sellable inventory are not observable and are not inferred.",
            "The probe localizes where the money gap is visible; it does not identify cause."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SB01_GAP_LOCALIZATION_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
