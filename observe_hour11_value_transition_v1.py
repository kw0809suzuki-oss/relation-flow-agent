#!/usr/bin/env python3
"""Observe the Day9 hour11 value conversion transition without daily compression.

Records exact pre-action MILK/WHEAT prices from Kaggriculture's market.prices map,
market actions, and next observed money. Observer only; Agent policy unchanged.
"""
import json
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base

TARGET_SEEDS = {3206, 3222, 3240, 3251, 3202, 3227, 3246, 3231}


def price_map(obs):
    # Official Kaggriculture observation schema: obs['market']['prices'].
    market = obs.get("market", {}) or {}
    prices = market.get("prices", {}) or {} if isinstance(market, dict) else {}
    return {str(k): float(v) for k, v in prices.items() if isinstance(v, (int, float))}


def listed_cash_effect(actions, prices):
    effect = 0.0
    parts = []
    for a in actions or []:
        if not isinstance(a, (list, tuple)) or len(a) < 3:
            continue
        verb, item, qty = a[0], str(a[1]), a[2]
        if not isinstance(qty, (int, float)) or item not in prices:
            continue
        p = prices[item]
        delta = float(qty) * p if verb == "SELL" else (-float(qty) * p if verb == "BUY_PRODUCT" else 0.0)
        if delta:
            effect += delta
            parts.append({"verb": verb, "item": item, "qty": float(qty), "price": p, "cash_effect": delta})
    return effect, parts


def main():
    rows = []
    for seed, seat in [(s, seat) for s, seat in base.DEFAULT_CASES if s in TARGET_SEEDS]:
        base._configure_baseline()
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        pending = None

        def observed(obs):
            nonlocal pending
            player = int(obs.get("player", seat))
            farm = (obs.get("farms", []) or [])[player]
            day, hour = int(obs.get("day", 0)), int(obs.get("hour", 0))
            money = float(farm.get("money", 0) or 0)
            if pending is not None:
                pending["next_day"] = day
                pending["next_hour"] = hour
                pending["money_next"] = money
                pending["money_delta_observed"] = money - pending["money_before"]
                pending["residual_vs_listed_cash"] = pending["money_delta_observed"] - pending["listed_cash_effect"]
                rows.append(pending)
                pending = None

            action = base.v6.agent(obs)
            if day == 9 and hour == 11:
                prices = price_map(obs)
                market = action.get("market", []) if isinstance(action, dict) else []
                implied, parts = listed_cash_effect(market, prices)
                pending = {
                    "seed": seed, "seat": seat, "day": day, "hour": hour,
                    "money_before": money,
                    "MILK_price": prices.get("MILK"),
                    "WHEAT_price": prices.get("WHEAT"),
                    "market_action": market,
                    "listed_cash_parts": parts,
                    "listed_cash_effect": implied,
                }
            return action

        players = [base.OPPONENT, base.OPPONENT]
        players[seat] = observed
        env.run(players)

    payload = {
        "coordinate": "AI Desk -> Day9 hour11 value conversion arrow",
        "policy_mutated": False,
        "purpose": "test whether pre-action MILK/WHEAT prices plus listed market actions account for the observed hour11 money transition",
        "boundary": "listed_cash_effect uses pre-action prices; engine processes market actions sequentially and refreshes prices after transactions, so residual is expected if within-step price movement matters and must not be causally assigned without further observation",
        "rows": rows,
    }
    Path("hour11_value_transition_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("HOUR11_VALUE_TRANSITION_V1 rows=" + str(len(rows)))

if __name__ == "__main__":
    main()
