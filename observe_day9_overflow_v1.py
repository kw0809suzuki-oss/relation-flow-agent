#!/usr/bin/env python3
"""Minimal observer for the Day9 end-of-day shed overflow candidate.

Observer only: does not mutate Agent policy. Keeps shed and carried inventory
separate so the Day9 -> Day10 transition can be checked without collapsing them.
"""
import json
from pathlib import Path
from typing import Any, Dict

from kaggle_environments import make
import export_scale_baseline_v1 as base

TARGET_SEEDS = {3206, 3222, 3240, 3227, 3251}
SHED_CAPACITY = 100


def numeric_total(store: Dict[str, Any]) -> float:
    return sum(float(v) for v in (store or {}).values() if isinstance(v, (int, float)))


def carried_total(private: Dict[str, Any]) -> float:
    return sum(numeric_total(inv) for inv in (private.get("inventories", []) or []) if isinstance(inv, dict))


def carried_qty(private: Dict[str, Any], product: str) -> float:
    return sum(float(inv.get(product, 0) or 0) for inv in (private.get("inventories", []) or []) if isinstance(inv, dict) and isinstance(inv.get(product, 0), (int, float)))


def snap(obs: Dict[str, Any]) -> Dict[str, Any]:
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    shed_total = numeric_total(shed)
    c_total = carried_total(private)
    room = max(0.0, SHED_CAPACITY - shed_total)
    c_milk = carried_qty(private, "MILK")
    # Exact product identity of discarded items can depend on engine drop ordering.
    # This is therefore only a capacity-risk marker, not causal attribution.
    return {
        "day": int(obs.get("day", 0)),
        "turn": obs.get("step"),
        "shed_total": shed_total,
        "shed_MILK": float(shed.get("MILK", 0) or 0),
        "carried_total": c_total,
        "carried_MILK": c_milk,
        "room": room,
        "overflow_total_candidate": max(0.0, c_total - room),
        "milk_at_risk_if_capacity_fills_first": max(0.0, c_milk - room),
    }


def play(seed: int, seat: int):
    base._configure_baseline()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    day9_last = None
    day10_first = None

    def observed(obs):
        nonlocal day9_last, day10_first
        row = snap(obs)
        if row["day"] == 9:
            day9_last = row
        elif row["day"] == 10 and day10_first is None:
            day10_first = row
        return base.v6.agent(obs)

    players = [base.OPPONENT, base.OPPONENT]
    players[seat] = observed
    env.run(players)
    return {"seed": seed, "seat": seat, "day9_last_observed": day9_last, "day10_first_observed": day10_first}


def main():
    cases = [(s, seat) for s, seat in base.DEFAULT_CASES if s in TARGET_SEEDS]
    rows = [play(seed, seat) for seed, seat in cases]
    payload = {
        "coordinate": "AI Desk -> Day9 State -> Agent Action -> [environment transition ?] -> Day10 State",
        "policy_mutated": False,
        "purpose": "test whether shed capacity overflow is consistent with the unexplained MILK disappearance without assuming it is the cause",
        "shed_capacity": SHED_CAPACITY,
        "boundary": "overflow_total_candidate proves only that total carried stock exceeds available shed room; product-level discard remains unconfirmed unless engine ordering/log evidence identifies it",
        "cases": rows,
    }
    Path("day9_overflow_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DAY9_OVERFLOW_V1 " + json.dumps(rows, separators=(",", ":")))


if __name__ == "__main__":
    main()
