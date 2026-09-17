#!/usr/bin/env python3
"""Trace only the market-state precursor of the Day9 hour11 MILK price split.

Observer only. For selected high/low cases, record turn-level MILK market inventory,
price, and the selected agent's MILK market actions through Day8-Day9 hour11.
This is intentionally the last reverse-trace observation before interpretation.
"""
import json
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base

HIGH = {3206, 3222, 3240, 3251}
LOW = {3202, 3227, 3246, 3231}
TARGET = HIGH | LOW


def main():
    rows = []
    for seed, seat in [(s, seat) for s, seat in base.DEFAULT_CASES if s in TARGET]:
        base._configure_baseline()
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)

        def observed(obs):
            day = int(obs.get("day", 0)); hour = int(obs.get("hour", 0))
            action = base.v6.agent(obs)
            if day == 8 or (day == 9 and hour <= 11):
                market = obs.get("market", {}) or {}
                prices = market.get("prices", {}) or {}
                inv = market.get("inventory", {}) or {}
                milk_actions = []
                if isinstance(action, dict):
                    for a in action.get("market", []) or []:
                        if isinstance(a, (list, tuple)) and len(a) >= 2 and str(a[1]) == "MILK":
                            milk_actions.append(list(a))
                rows.append({
                    "seed": seed, "group": "high" if seed in HIGH else "low",
                    "seat": seat, "day": day, "hour": hour,
                    "MILK_market_inventory": inv.get("MILK"),
                    "MILK_price": prices.get("MILK"),
                    "self_MILK_market_actions": milk_actions,
                })
            return action

        players = [base.OPPONENT, base.OPPONENT]; players[seat] = observed
        env.run(players)

    Path("milk_price_precursor_v1.json").write_text(json.dumps({
        "coordinate": "AI Desk -> precursor of Day9 hour11 MILK price split",
        "policy_mutated": False,
        "boundary": "Market inventory is shared system state. Self MILK actions are recorded for alignment only; changes in shared inventory cannot be attributed to self without observing all market participants/environment processing.",
        "rows": rows,
    }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("MILK_PRICE_PRECURSOR_V1 rows=" + str(len(rows)))

if __name__ == "__main__": main()
