#!/usr/bin/env python3
"""Turn-level MILK flow observer around the P12 terminal split.

Observation only. Replays WR-02 and WR-02+P12 on the same Fresh20 cases.
Records Day18..21 MILK market state plus the selected agent's own market actions.
Shared-market changes are not attributed to self without all-participant action evidence.
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
OUT = Path(f"p12_milk_flow_observer_v0_{SEED}_seat{SEAT}.json")
TARGET_DAYS = {18, 19, 20, 21}


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def count_cows(farm):
    n = 0
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                n += 1
    return n


def private_qty(priv, item):
    total = 0.0
    shed = priv.get("shed", {}) or {}
    total += float(shed.get(item, 0) or 0)
    for inv in priv.get("inventories", []) or []:
        if isinstance(inv, dict):
            total += float(inv.get(item, 0) or 0)
    return total


def market_units(action, op, item):
    total = 0.0
    if not isinstance(action, dict):
        return total
    for a in action.get("market", []) or []:
        if not isinstance(a, (list, tuple)) or not a:
            continue
        if a[0] != op:
            continue
        if op == "SELL":
            if len(a) >= 3 and str(a[1]) == item:
                total += float(a[2] or 0)
        elif op == "BUY_ANIMAL":
            if len(a) >= 3 and str(a[1]) == item:
                total += float(a[2] or 0)
    return total


def play(module):
    configure()
    module.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    rows = []
    cumulative_sell_milk = 0.0
    cumulative_buy_cow = 0.0

    def observed(obs):
        nonlocal cumulative_sell_milk, cumulative_buy_cow
        action = module.agent(obs)
        sell_milk = market_units(action, "SELL", "MILK")
        buy_cow = market_units(action, "BUY_ANIMAL", "COW")
        cumulative_sell_milk += sell_milk
        cumulative_buy_cow += buy_cow

        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        if day in TARGET_DAYS:
            player = int(obs.get("player", SEAT))
            farms = obs.get("farms", []) or []
            farm = farms[player]
            opp = farms[1 - player]
            priv = obs.get("private", {}) or {}
            market = obs.get("market", {}) or {}
            inv = market.get("inventory", {}) or {}
            prices = market.get("prices", {}) or {}
            rows.append({
                "day": day,
                "hour": hour,
                "self_cash": float(farm.get("money", 0) or 0),
                "opponent_cash": float(opp.get("money", 0) or 0),
                "self_cows": count_cows(farm),
                "self_milk_qty": private_qty(priv, "MILK"),
                "self_wheat_qty": private_qty(priv, "WHEAT"),
                "market_inventory_milk": float(inv.get("MILK", 0) or 0),
                "market_price_milk": float(prices.get("MILK", 0) or 0),
                "self_sell_milk_this_turn": sell_milk,
                "self_buy_cow_this_turn": buy_cow,
                "self_cumulative_sell_milk": cumulative_sell_milk,
                "self_cumulative_buy_cow": cumulative_buy_cow,
                "self_market_actions": action.get("market", []) if isinstance(action, dict) else [],
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
    b = play(current)
    c = play(candidate)
    payload = {
        "schema": "kaggriculture.p12-milk-flow-observer.v0",
        "seed": SEED,
        "seat": SEAT,
        "current": b,
        "candidate": c,
        "delta_self": c["terminal"]["self"] - b["terminal"]["self"],
        "delta_margin": c["terminal"]["margin"] - b["terminal"]["margin"],
        "boundary": [
            "Observation-only replay; no policy mutation.",
            "Shared MILK market inventory/price reflects all participants and environment processing.",
            "Only the selected agent's own market actions are directly attributed here.",
            "Cumulative SELL MILK and BUY COW counters start at Day0 even though rows are emitted only for Day18..21.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("P12_MILK_FLOW_OBSERVER " + json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "rows_current": len(b["rows"]),
        "rows_candidate": len(c["rows"]),
        "delta_self": payload["delta_self"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
