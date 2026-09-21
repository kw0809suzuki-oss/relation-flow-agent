#!/usr/bin/env python3
"""Observation-only Day 6->8 action composition probe for fixed SB-01.

No strategy or candidate behavior is changed.
Collects action composition seen on the self side during Day 6 and Day 7,
plus first state observations on Day 6 and Day 8 for alignment.
Opponent internal action stream is not directly observable here and is not inferred.
"""
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
OUT = Path(f"sb01_day6_8_actions_{SEED}.json")


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def _public_assets(farm):
    crops, animals = {}, {}
    active_tiles = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile == "LOCKED" or tile is None:
                continue
            active_tiles += 1
            if isinstance(tile, dict):
                if tile.get("crop"):
                    crops[tile["crop"]] = crops.get(tile["crop"], 0) + 1
                if tile.get("animal"):
                    animals[tile["animal"]] = animals.get(tile["animal"], 0) + 1
    return {
        "active_tiles": active_tiles,
        "crops": crops,
        "animals": animals,
        "production_asset_count": sum(crops.values()) + sum(animals.values()),
    }


def _state(obs):
    p = int(obs["player"])
    me = obs["farms"][p]
    opp = obs["farms"][1-p]
    return {
        "day": int(obs.get("day", 0) or 0),
        "self_money": float(me.get("money", 0) or 0),
        "opponent_money": float(opp.get("money", 0) or 0),
        "self_assets": _public_assets(me),
        "opponent_assets": _public_assets(opp),
    }


def _market_key(order):
    if not isinstance(order, (list, tuple)) or not order:
        return "INVALID"
    op = str(order[0])
    args = ":".join(str(x) for x in order[1:3])
    return op + (":" + args if args else "")


def _simple_key(action):
    if isinstance(action, str):
        return action
    if isinstance(action, (list, tuple)):
        return ":".join(str(x) for x in action[:3])
    if action is None:
        return "NONE"
    return str(action)


def main():
    configure()
    states = {}
    counts = {
        "day6": {"market": Counter(), "farmer": Counter(), "hands": Counter(), "calls": 0},
        "day7": {"market": Counter(), "farmer": Counter(), "hands": Counter(), "calls": 0},
    }

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]

    def observed(obs):
        day = int(obs.get("day", 0) or 0)
        if day in (6, 8) and str(day) not in states:
            states[str(day)] = _state(obs)

        action = combat.agent(obs)

        if day in (6, 7):
            key = "day6" if day == 6 else "day7"
            counts[key]["calls"] += 1
            if isinstance(action, dict):
                for order in action.get("market", []) or []:
                    counts[key]["market"][_market_key(order)] += 1
                counts[key]["farmer"][_simple_key(action.get("farmer"))] += 1
                for hand in action.get("hands", []) or []:
                    counts[key]["hands"][_simple_key(hand)] += 1
        return action

    players[SEAT] = observed
    env.run(players)

    payload = {
        "schema": "kaggriculture.sb01.day6-8-action-composition.v0",
        "probe": "Remaining Strength Gap Day6-8 Action Composition",
        "mode": "observation_only_replay",
        "seed": SEED,
        "seat": SEAT,
        "snapshot": "SB-01",
        "states": states,
        "actions": {
            day: {
                "calls": d["calls"],
                "market": dict(d["market"]),
                "farmer": dict(d["farmer"]),
                "hands": dict(d["hands"]),
            }
            for day, d in counts.items()
        },
        "boundary": [
            "No strategy, rule, threshold, or candidate is changed.",
            "Uses exact fixed SB-01 seed/seat/opponent/runtime conditions.",
            "Only self-side emitted actions during Day 6 and Day 7 are counted.",
            "Opponent internal action stream is unavailable in this probe and is not inferred.",
            "This probe identifies action composition near the first asset split; it does not establish cause."
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SB01_DAY6_8_ACTION_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
