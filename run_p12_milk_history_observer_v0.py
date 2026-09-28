#!/usr/bin/env python3
"""Observation-only P12 MILK market history from Day0 through Day19.

Purpose:
Locate when the later Day19 Hour17 MILK market stratification first becomes
visible. This probe records only shared MILK market inventory/price and the
terminal delta used to form the already-observed improved/worsened groups.

It does not attribute cause, inspect actions, or mutate policy.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import wr02_same_tile_plant_deconfliction_v0 as current
import wr02_p12_day0_reservation_v0 as candidate

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"p12_milk_history_observer_v0_{SEED}_seat{SEAT}.json")
MAX_DAY = 19


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def play(module):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)

    rows = []

    def observed(obs):
        action = module.agent(obs)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        if day <= MAX_DAY:
            market = obs.get("market", {}) or {}
            inventory = market.get("inventory", {}) or {}
            prices = market.get("prices", {}) or {}
            rows.append({
                "day": day,
                "hour": hour,
                "market_inventory_milk": float(inventory.get("MILK", 0) or 0),
                "market_price_milk": float(prices.get("MILK", 0) or 0),
            })
        return action

    players = [basecfg.OPPONENT, basecfg.OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(x.reward) for x in env.state]
    return {
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "rows": rows,
    }


def main():
    baseline = play(current)
    p12 = play(candidate)
    payload = {
        "schema": "kaggriculture.p12-milk-history-observer.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": baseline,
        "candidate": p12,
        "delta_self": p12["terminal"]["self"] - baseline["terminal"]["self"],
        "delta_margin": p12["terminal"]["margin"] - baseline["terminal"]["margin"],
        "boundary": [
            "Observation-only replay; no policy mutation.",
            "Only shared MILK market inventory and price are retained through Day19.",
            "Terminal improved/worsened grouping is descriptive and is not used by either agent during replay.",
            "No action, resolver event, participant contribution, or causal mechanism is inferred.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("P12_MILK_HISTORY_OBSERVER " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "rows_current": len(baseline["rows"]),
        "rows_candidate": len(p12["rows"]),
        "delta_self": payload["delta_self"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
