#!/usr/bin/env python3
"""Export v6-only observations for Scale Chassis ROI estimation.

This exporter does not alter policy. It wraps the existing agent, records only
state fields that are observable at runtime, and writes one daily row per game.
Unknown/unavailable dimensions are kept explicit instead of guessed.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from kaggle_environments import make

import agent as v6


OPPONENT = "opponents/seyamalam_v21.py"
DEFAULT_CASES = (
    (4092, 0), (4093, 1), (4094, 0), (4095, 1), (4096, 0),
    (4097, 1), (4098, 0), (4099, 1), (4100, 0), (4101, 1),
)


def _count_animals(farm: Dict[str, Any]):
    # Kaggriculture schemas used across experiments have varied. Do not infer.
    for key in ("animals", "livestock"):
        value = farm.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return sum(int(v) for v in value.values() if isinstance(v, (int, float)))
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _inventory_value(private: Dict[str, Any], prices: Dict[str, Any]):
    # Conservative proxy for value already produced but not yet collected as cash.
    inventory = private.get("inventory") or private.get("products")
    if not isinstance(inventory, dict):
        return None
    total = 0.0
    seen = False
    for key, amount in inventory.items():
        if not isinstance(amount, (int, float)):
            continue
        price = prices.get(key)
        if isinstance(price, (int, float)):
            total += float(amount) * float(price)
            seen = True
    return total if seen else None


def _snapshot(obs: Dict[str, Any]) -> Dict[str, Any]:
    player = obs["player"]
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    prices = obs.get("market", {}).get("prices", {}) or {}
    return {
        "day": int(obs.get("day", 0)),
        "money": float(farm.get("money", 0.0)),
        "land": len(farm.get("unlocked_quadrants", [])),
        "hands": len(farm.get("hands", [])),
        "animals": _count_animals(farm),
        "inventory_value": _inventory_value(private, prices),
    }


def play(seed: int, seat: int) -> Dict[str, Any]:
    v6.reset_trace()
    v6.reset_telemetry()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    snapshots: List[Dict[str, Any]] = []
    last_day = None

    def observed(obs):
        nonlocal last_day
        row = _snapshot(obs)
        if row["day"] != last_day:
            snapshots.append(row)
            last_day = row["day"]
        else:
            snapshots[-1] = row
        return v6.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]

    # Derive realized daily cash collection from money deltas only; production is
    # kept separate/unknown unless observable. Negative deltas are not collection.
    rows = []
    prev_money = None
    for snap in snapshots:
        collected = 0.0 if prev_money is None else max(0.0, snap["money"] - prev_money)
        prev_money = snap["money"]
        rows.append({
            "day": snap["day"],
            "money": snap["money"],
            "land": snap["land"],
            "hands": snap["hands"],
            "animals": snap["animals"],
            "produced_value": snap["inventory_value"],
            "collected_value": collected,
        })

    return {
        "seed": seed,
        "seat": seat,
        "terminal": {
            "self": float(rewards[seat]),
            "opponent": float(rewards[1-seat]),
            "margin": float(rewards[seat]) - float(rewards[1-seat]),
        },
        "observations": rows,
        "missing": {
            "animals": any(row["animals"] is None for row in rows),
            "produced_value": any(row["produced_value"] is None for row in rows),
        },
    }


def main():
    results = [play(seed, seat) for seed, seat in DEFAULT_CASES]
    payload = {
        "schema": "kaggriculture.scale-chassis-baseline.v1",
        "policy_mutated": False,
        "cases": results,
        "notes": [
            "collected_value is realized positive daily money delta, not causal profit attribution",
            "animals/produced_value remain null when unavailable; no value is guessed",
        ],
    }
    Path("scale_baseline_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SCALE_BASELINE_V1 " + json.dumps({"cases": len(results)}, separators=(",", ":")))


if __name__ == "__main__":
    main()
