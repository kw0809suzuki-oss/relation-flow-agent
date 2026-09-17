#!/usr/bin/env python3
"""Reverse-trace the Day15 MILK divergence without mutating policy.

Coordinate:
terminal self -> throughput divergence -> Day15 MILK stock decrease
-> trace backward Cow / MILK stock / feed-related observable state.

Stop at the earliest observed group divergence. Descriptive only; no causality claim.
"""
import json
from pathlib import Path
from typing import Any, Dict

import export_scale_baseline_v1 as base
from kaggle_environments import make

DAYS = set(range(8, 16))


def _sum_named(store, name):
    if not isinstance(store, dict):
        return 0.0
    v = store.get(name, 0)
    return float(v) if isinstance(v, (int, float)) else 0.0


def snapshot(obs: Dict[str, Any]) -> Dict[str, Any]:
    player = obs["player"]
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    invs = list(private.get("inventories", []) or [])
    stores = [shed] + invs

    milk = sum(_sum_named(s, "MILK") for s in stores)
    wheat = sum(_sum_named(s, "WHEAT") for s in stores)

    animals = farm.get("animals", []) or []
    cows = 0
    fed_cows = 0
    cared_cows = 0
    for a in animals:
        if not isinstance(a, dict) or a.get("type") != "COW":
            continue
        cows += 1
        if a.get("fed") is True or a.get("is_fed") is True:
            fed_cows += 1
        if a.get("cared") is True or a.get("is_cared") is True:
            cared_cows += 1

    return {
        "day": int(obs.get("day", 0)),
        "money": float(farm.get("money", 0.0)),
        "cows": cows,
        "fed_cows_observed": fed_cows,
        "cared_cows_observed": cared_cows,
        "milk_qty": milk,
        "wheat_qty": wheat,
    }


def play(seed: int, seat: int):
    base._configure_baseline()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    snaps = []
    last_day = None

    def observed(obs):
        nonlocal last_day
        row = snapshot(obs)
        if row["day"] in DAYS:
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
    return {"seed": seed, "seat": seat, "terminal_self": float(rewards[seat]), "days": snaps}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    cases = [play(seed, seat) for seed, seat in base.DEFAULT_CASES]
    ranked = sorted(cases, key=lambda x: x["terminal_self"], reverse=True)
    high, low = ranked[:4], ranked[-4:]

    def group(rows):
        by_day = {}
        for day in sorted(DAYS):
            ds = [d for r in rows for d in r["days"] if d["day"] == day]
            by_day[str(day)] = {
                "money": mean([d["money"] for d in ds]),
                "cows": mean([d["cows"] for d in ds]),
                "fed_cows_observed": mean([d["fed_cows_observed"] for d in ds]),
                "cared_cows_observed": mean([d["cared_cows_observed"] for d in ds]),
                "milk_qty": mean([d["milk_qty"] for d in ds]),
                "wheat_qty": mean([d["wheat_qty"] for d in ds]),
            }
        return by_day

    payload = {
        "coordinate": "Day15 MILK difference -> reverse trace Day8-15 Cow/MILK/feed-related observable state",
        "policy_mutated": False,
        "boundary": "fed/cared fields are recorded only if exposed by the environment schema; zeros may mean unavailable, not absence. Group differences are descriptive, not causal.",
        "high_seeds": [r["seed"] for r in high],
        "low_seeds": [r["seed"] for r in low],
        "high": group(high),
        "low": group(low),
        "cases": cases,
    }
    Path("milk_precursor_v1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MILK_PRECURSOR_V1 " + json.dumps({"high": payload["high"], "low": payload["low"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
