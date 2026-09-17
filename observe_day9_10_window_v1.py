#!/usr/bin/env python3
"""Observe the open Day9->10 divergence window without mutating policy.

Keep the coordinate fixed while leaving the route open: capture money, product stock,
market prices, and the agent's returned market actions around Day9/10. Descriptive only.
"""
import json
from pathlib import Path
from typing import Any, Dict

import export_scale_baseline_v1 as base
from kaggle_environments import make

DAYS = {8, 9, 10, 11}
PRODUCTS = ("WHEAT", "STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "FERTILIZER")


def _qty(private, product):
    stores = [private.get("shed", {}) or {}] + list(private.get("inventories", []) or [])
    total = 0.0
    for store in stores:
        if isinstance(store, dict) and isinstance(store.get(product), (int, float)):
            total += float(store[product])
    return total


def snapshot(obs: Dict[str, Any]) -> Dict[str, Any]:
    player = obs["player"]
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    prices = obs.get("market", {}).get("prices", {}) or {}
    return {
        "day": int(obs.get("day", 0)),
        "money": float(farm.get("money", 0.0)),
        "qty": {p: _qty(private, p) for p in PRODUCTS},
        "prices": {p: float(prices[p]) for p in PRODUCTS if isinstance(prices.get(p), (int, float))},
    }


def play(seed: int, seat: int):
    base._configure_baseline()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    rows = []
    last_day = None

    def observed(obs):
        nonlocal last_day
        row = snapshot(obs)
        action = base.v6.agent(obs)
        row["market_actions"] = action.get("market", []) if isinstance(action, dict) else []
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

    transitions = []
    for prev, cur in zip(rows, rows[1:]):
        if cur["day"] not in {9, 10, 11}:
            continue
        decreases = {}
        for p in PRODUCTS:
            dq = cur["qty"].get(p, 0.0) - prev["qty"].get(p, 0.0)
            if dq < 0:
                decreases[p] = {
                    "qty_delta": dq,
                    "prev_price": prev["prices"].get(p),
                    "cur_price": cur["prices"].get(p),
                }
        transitions.append({
            "from_day": prev["day"],
            "to_day": cur["day"],
            "money_before": prev["money"],
            "money_after": cur["money"],
            "money_delta": cur["money"] - prev["money"],
            "actions_returned_at_from_day": prev.get("market_actions", []),
            "product_stock_decreases": decreases,
        })
    return {"seed": seed, "seat": seat, "terminal_self": float(rewards[seat]), "days": rows, "transitions": transitions}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    cases = [play(seed, seat) for seed, seat in base.DEFAULT_CASES]
    ranked = sorted(cases, key=lambda x: x["terminal_self"], reverse=True)
    high, low = ranked[:4], ranked[-4:]

    def group(rows):
        out = {}
        for to_day in (9, 10, 11):
            ts = [t for r in rows for t in r["transitions"] if t["to_day"] == to_day]
            out[str(to_day)] = {
                "mean_money_delta": mean([t["money_delta"] for t in ts]),
                "returned_market_actions": [
                    {"seed": r["seed"], "actions": next((t["actions_returned_at_from_day"] for t in r["transitions"] if t["to_day"] == to_day), [])}
                    for r in rows
                ],
                "stock_decreases": [
                    {"seed": r["seed"], "decreases": next((t["product_stock_decreases"] for t in r["transitions"] if t["to_day"] == to_day), {})}
                    for r in rows
                ],
            }
        return out

    payload = {
        "coordinate": "Day9 nearly equal -> Day10 high group about +1k ahead; observe the surrounding transition without preselecting a cause",
        "policy_mutated": False,
        "boundary": "returned actions, stock movement, prices and money deltas are descriptive observations; temporal connection does not by itself prove causal revenue identity",
        "high_seeds": [r["seed"] for r in high],
        "low_seeds": [r["seed"] for r in low],
        "high": group(high),
        "low": group(low),
        "cases": cases,
    }
    Path("day9_10_window_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DAY9_10_WINDOW_V1 " + json.dumps({"high": payload["high"], "low": payload["low"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
