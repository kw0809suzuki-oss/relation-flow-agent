#!/usr/bin/env python3
"""Export observations from the existing whole-flow OFF baseline for Scale Chassis.

Keep this deliberately simple: use the same known cases and OFF configuration as
run_whole_flow_control.py, then expose daily observations for Scale Chassis.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from kaggle_environments import make

import whole_flow_control_agent as v6


OPPONENT = "opponents/seyamalam_v21.py"
# Same cases as run_whole_flow_control.py. This avoids changing both the agent
# identity and the evaluation cases while repairing the Scale observation path.
DEFAULT_CASES = (
    (3202, 0), (3206, 0), (3215, 1), (3218, 0),
    (3222, 0), (3227, 1), (3231, 1), (3240, 0),
    (3243, 1), (3246, 0), (3250, 0), (3251, 1),
)


def _configure_baseline():
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    v6.set_control_enabled(False)
    v6.set_probe_enabled(True)
    v6.set_attribution_enabled(True)
    v6.reset_telemetry()


def _count_animals(farm: Dict[str, Any]):
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
    _configure_baseline()
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
        "baseline_identity": "whole_flow_control_agent control OFF; same cases/configuration as run_whole_flow_control.py",
        "policy_mutated": False,
        "cases": results,
        "notes": [
            "repair run uses the known whole-flow comparison cases before returning to Scale Chassis",
            "collected_value is realized positive daily money delta, not causal profit attribution",
            "animals/produced_value remain null when unavailable; no value is guessed",
        ],
    }
    Path("scale_baseline_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    values = [row["terminal"]["self"] for row in results]
    summary = {
        "cases": len(results),
        "mean_self": sum(values) / len(values),
        "min_self": min(values),
        "max_self": max(values),
    }
    print("SCALE_BASELINE_V1 " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
