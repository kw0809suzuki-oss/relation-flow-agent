#!/usr/bin/env python3
"""Observation-only daily trajectory for WR-02 vs WR-02+P12 on Fresh20.

No policy change. Replays the existing paired comparison and records the first
officially observed state of each day 0..29 for both sides.
"""
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_p12_day0_reservation_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"p12_trajectory_divergence_observer_v0_{SEED}_seat{SEAT}.json")
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ANIMALS = ("GOOSE", "COW", "SHEEP")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if hasattr(v, "items"):
        try:
            return {str(k): plain(x) for k, x in v.items()}
        except Exception:
            pass
    if hasattr(v, "tolist"):
        try:
            return plain(v.tolist())
        except Exception:
            pass
    if hasattr(v, "item"):
        try:
            return plain(v.item())
        except Exception:
            pass
    if hasattr(v, "__dict__"):
        try:
            return {str(k): plain(x) for k, x in vars(v).items()}
        except Exception:
            pass
    return repr(v)


def getv(x, key, default=None):
    if isinstance(x, dict):
        return x.get(key, default)
    try:
        return getattr(x, key)
    except Exception:
        return default


def farm_summary(farm):
    crops = Counter()
    animals = Counter()
    unlocked = 0
    empty = 0
    occupied = 0
    plant_tiles = 0
    weed_tiles = 0
    structure_tiles = 0
    animal_tiles = 0
    harvestable_plant_tiles = 0
    animal_yield_units = 0
    plant_yield_units = 0

    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if tile == "LOCKED":
                continue
            unlocked += 1
            if tile is None:
                empty += 1
                continue
            occupied += 1
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "PLANT":
                plant_tiles += 1
                crop = tile.get("crop")
                if crop:
                    crops[str(crop)] += 1
                yu = float(tile.get("yield_units", 0) or 0)
                plant_yield_units += yu
                if yu > 0:
                    harvestable_plant_tiles += 1
            elif kind == "WEED":
                weed_tiles += 1
            elif kind in ("COOP", "PASTURE"):
                structure_tiles += 1
                animal = tile.get("animal")
                if animal:
                    animal_tiles += 1
                    animals[str(animal)] += 1
                    animal_yield_units += float(tile.get("yield_units", 0) or 0)

    hands = farm.get("hands", []) or []
    return {
        "cash": float(farm.get("money", 0) or 0),
        "unlocked_tiles": unlocked,
        "empty_tiles": empty,
        "occupied_unlocked": occupied,
        "plant_tiles": plant_tiles,
        "weed_tiles": weed_tiles,
        "structure_tiles": structure_tiles,
        "animal_tiles": animal_tiles,
        "harvestable_plant_tiles": harvestable_plant_tiles,
        "plant_yield_units": plant_yield_units,
        "animal_yield_units": animal_yield_units,
        "workers": 1 + len(hands),
        "hands": len(hands),
        "unlocked_quadrants": list(farm.get("unlocked_quadrants", []) or []),
        "crop_count": {c: int(crops.get(c, 0)) for c in CROPS},
        "animal_count": {a: int(animals.get(a, 0)) for a in ANIMALS},
    }


def private_summary(priv):
    shed = dict(priv.get("shed", {}) or {})
    seeds = dict(priv.get("seeds", {}) or {})
    inventories = list(priv.get("inventories", []) or [])

    shed_total = sum(float(v or 0) for v in shed.values())
    carried_total = 0.0
    for inv in inventories:
        if isinstance(inv, dict):
            carried_total += sum(float(v or 0) for v in inv.values())

    return {
        "seeds": {c: float(seeds.get(c, 0) or 0) for c in CROPS},
        "shed": {str(k): float(v or 0) for k, v in shed.items()},
        "shed_total_units": shed_total,
        "carried_total_units": carried_total,
        "actor_inventory_count": len(inventories),
    }


def market_summary(market):
    prices = market.get("prices", {}) or {}
    inventory = market.get("inventory", {}) or {}
    return {
        "prices": {str(k): float(v or 0) for k, v in prices.items()},
        "inventory": {str(k): float(v or 0) for k, v in inventory.items()},
    }


def obs_summary(obs):
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", SEAT))
    other = 1 - player
    return {
        "day": int(obs.get("day", 0) or 0),
        "hour": int(obs.get("hour", 0) or 0),
        "step": obs.get("step"),
        "self": farm_summary(farms[player]) if player < len(farms) else None,
        "opponent": farm_summary(farms[other]) if other < len(farms) else None,
        "private": private_summary(obs.get("private", {}) or {}),
        "market": market_summary(obs.get("market", {}) or {}),
        "town": plain(obs.get("town", {}) or {}),
    }


def play(module):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = module.agent
    env.run(players)

    daily = {}
    for step in getattr(env, "steps", []) or []:
        if not isinstance(step, (list, tuple)) or len(step) <= SEAT:
            continue
        obs = plain(getv(step[SEAT], "observation"))
        if not isinstance(obs, dict):
            continue
        day = int(obs.get("day", 0) or 0)
        key = str(day)
        if key in daily:
            continue
        daily[key] = obs_summary(obs)

    rewards = [float(x.reward) for x in env.state]
    return {
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "days": daily,
    }


def main():
    b = play(current)
    c = play(candidate)
    payload = {
        "schema": "kaggriculture.p12-trajectory-divergence-observer.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": b,
        "candidate": c,
        "delta_self": c["terminal"]["self"] - b["terminal"]["self"],
        "delta_margin": c["terminal"]["margin"] - b["terminal"]["margin"],
        "boundary": [
            "Observation-only replay of existing WR-02 vs WR-02+P12 Fresh20.",
            "No policy logic is changed.",
            "Daily state is the first observation available to the candidate seat on each day.",
            "All farm metrics are direct counts/sums from the official visible state; no terminal-value interpretation is added.",
            "Terminal outcome labels are not used to alter capture."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("P12_TRAJECTORY_OBSERVER " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "days_current": sorted(map(int, b["days"].keys())),
        "days_candidate": sorted(map(int, c["days"].keys())),
        "delta_self": payload["delta_self"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
