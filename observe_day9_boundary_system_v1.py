#!/usr/bin/env python3
"""Observe the Day8-10 system boundary without preselecting MILK or any cause."""
import json
from pathlib import Path
from typing import Any, Dict

import export_scale_baseline_v1 as base
from kaggle_environments import make

DAYS = {8, 9, 10}
PRODUCTS = ("WHEAT", "STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "FERTILIZER")


def qty(private, product):
    stores = [private.get("shed", {}) or {}] + list(private.get("inventories", []) or [])
    return sum(float(s.get(product, 0) or 0) for s in stores if isinstance(s, dict) and isinstance(s.get(product, 0), (int, float)))


def snapshot(obs: Dict[str, Any]):
    player = obs["player"]
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    prices = obs.get("market", {}).get("prices", {}) or {}
    return {
        "day": int(obs.get("day", 0)),
        "money": float(farm.get("money", 0)),
        "land": len(farm.get("unlocked_quadrants", []) or []),
        "hands": len(farm.get("hands", []) or []),
        "animals": base._count_animals(farm),
        "inventory_value": base._product_stock_value(private, prices),
        "qty": {p: qty(private, p) for p in PRODUCTS},
        "prices": {p: float(prices[p]) for p in PRODUCTS if isinstance(prices.get(p), (int, float))},
    }


def play(seed, seat):
    base._configure_baseline()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    rows, last_day = [], None

    def observed(obs):
        nonlocal last_day
        row = snapshot(obs)
        action = base.v6.agent(obs)
        row["market_actions"] = action.get("market", []) if isinstance(action, dict) else []
        row["farm_actions"] = action.get("farm", []) if isinstance(action, dict) else []
        if row["day"] in DAYS:
            if row["day"] != last_day:
                rows.append(row)
                last_day = row["day"]
            else:
                rows[-1] = row
        return action

    players = [base.OPPONENT, base.OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {"seed": seed, "seat": seat, "terminal_self": float(rewards[seat]), "days": rows}


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def group(rows):
    out = {}
    for day in (8, 9, 10):
        ds = [next((d for d in r["days"] if d["day"] == day), None) for r in rows]
        ds = [d for d in ds if d]
        out[str(day)] = {
            "mean_money": mean([d["money"] for d in ds]),
            "mean_land": mean([d["land"] for d in ds]),
            "mean_hands": mean([d["hands"] for d in ds]),
            "mean_animals": mean([d["animals"] for d in ds if d["animals"] is not None]),
            "mean_inventory_value": mean([d["inventory_value"] for d in ds]),
            "mean_qty": {p: mean([d["qty"][p] for d in ds]) for p in PRODUCTS},
            "mean_prices": {p: mean([d["prices"].get(p) for d in ds if p in d["prices"]]) for p in PRODUCTS},
            "cases": [{"seed": r["seed"], "state": next((d for d in r["days"] if d["day"] == day), None)} for r in rows],
        }
    return out


def main():
    cases = [play(seed, seat) for seed, seat in base.DEFAULT_CASES]
    ranked = sorted(cases, key=lambda x: x["terminal_self"], reverse=True)
    high, low = ranked[:4], ranked[-4:]
    payload = {
        "coordinate": "Day8-10 whole-system boundary immediately before first thick money divergence",
        "policy_mutated": False,
        "cause_preselected": False,
        "boundary": "group differences are descriptive; no asset, product, price or action is causal merely because it precedes Day10 money divergence",
        "high_seeds": [r["seed"] for r in high],
        "low_seeds": [r["seed"] for r in low],
        "high": group(high),
        "low": group(low),
        "cases": cases,
    }
    Path("day9_boundary_system_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DAY9_BOUNDARY_SYSTEM_V1 " + json.dumps({"high_seeds": payload["high_seeds"], "low_seeds": payload["low_seeds"], "high": payload["high"], "low": payload["low"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
