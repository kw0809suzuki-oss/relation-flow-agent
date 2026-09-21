#!/usr/bin/env python3
"""Observe only the Day15/17 liquidation identity on the existing 12-case baseline.

No policy mutation. This is the next Re-entry step after Divergence Band v1:
30 days -> Day14-18 -> Day15/17 money-flow events -> which harvested products left stock.

A product stock decrease is descriptive evidence of inventory leaving the observed
shed+carried stores; it is not by itself causal proof of a SELL action or profit.
"""
import json
from pathlib import Path
from typing import Any, Dict

import export_scale_baseline_v1 as base
from kaggle_environments import make

TARGET_DAYS = {15, 17}
PRODUCTS = ("WHEAT", "STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "FERTILIZER")


def product_snapshot(obs: Dict[str, Any]) -> Dict[str, Any]:
    player = obs["player"]
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    prices = obs.get("market", {}).get("prices", {}) or {}
    stores = [private.get("shed", {}) or {}] + list(private.get("inventories", []) or [])
    qty = {p: 0.0 for p in PRODUCTS}
    for store in stores:
        if not isinstance(store, dict):
            continue
        for p in PRODUCTS:
            v = store.get(p, 0)
            if isinstance(v, (int, float)):
                qty[p] += float(v)
    return {
        "day": int(obs.get("day", 0)),
        "money": float(farm.get("money", 0.0)),
        "qty": qty,
        "prices": {p: float(prices[p]) for p in PRODUCTS if isinstance(prices.get(p), (int, float))},
    }


def play(seed: int, seat: int) -> Dict[str, Any]:
    base._configure_baseline()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    snaps = []
    last_day = None

    def observed(obs):
        nonlocal last_day
        row = product_snapshot(obs)
        if row["day"] != last_day:
            snaps.append(row)
            last_day = row["day"]
        else:
            snaps[-1] = row
        return base.v6.agent(obs)

    players = [base.OPPONENT, base.OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]

    events = []
    for prev, cur in zip(snaps, snaps[1:]):
        if cur["day"] not in TARGET_DAYS:
            continue
        money_delta = cur["money"] - prev["money"]
        decreases = {}
        for p in PRODUCTS:
            dq = cur["qty"].get(p, 0.0) - prev["qty"].get(p, 0.0)
            if dq < 0:
                decreases[p] = {
                    "qty_delta": dq,
                    "prev_qty": prev["qty"].get(p, 0.0),
                    "cur_qty": cur["qty"].get(p, 0.0),
                    "cur_price": cur["prices"].get(p),
                    "value_at_cur_price": (-dq) * cur["prices"].get(p, 0.0),
                }
        events.append({
            "day": cur["day"],
            "money_before": prev["money"],
            "money_after": cur["money"],
            "money_delta": money_delta,
            "product_stock_decreases": decreases,
        })
    return {"seed": seed, "seat": seat, "terminal_self": float(rewards[seat]), "events": events}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    cases = [play(seed, seat) for seed, seat in base.DEFAULT_CASES]
    ranked = sorted(cases, key=lambda x: x["terminal_self"], reverse=True)
    high, low = ranked[:4], ranked[-4:]

    def group(rows):
        out = {}
        for day in sorted(TARGET_DAYS):
            evs = [e for r in rows for e in r["events"] if e["day"] == day]
            product_values = {p: [] for p in PRODUCTS}
            product_cases = {p: 0 for p in PRODUCTS}
            for e in evs:
                for p in PRODUCTS:
                    info = e["product_stock_decreases"].get(p)
                    v = info["value_at_cur_price"] if info else 0.0
                    product_values[p].append(v)
                    if info:
                        product_cases[p] += 1
            out[str(day)] = {
                "mean_money_delta": mean([e["money_delta"] for e in evs]),
                "product_decrease_mean_value": {p: mean(vs) for p, vs in product_values.items() if any(vs)},
                "product_decrease_case_count": {p: n for p, n in product_cases.items() if n},
            }
        return out

    payload = {
        "coordinate": "Day15/17 money-flow events -> harvested-product stock decreases",
        "policy_mutated": False,
        "boundary": "stock decrease is descriptive inventory movement; it does not prove exact SELL revenue or causality",
        "high_seeds": [r["seed"] for r in high],
        "low_seeds": [r["seed"] for r in low],
        "high": group(high),
        "low": group(low),
        "cases": cases,
    }
    Path("liquidation_identity_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("LIQUIDATION_IDENTITY_V1 " + json.dumps({"high": payload["high"], "low": payload["low"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
