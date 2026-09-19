#!/usr/bin/env python3
"""Economic Observer sidecar — Current Combat Model fresh10.

No intervention. The agent action is returned unchanged.
Comparable scope is only SEED vs COW, matching the Drive v0.1 sheet.
"""

import copy
import json
import math
import os
import statistics
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

OPPONENT = base.OPPONENT
OPPONENT_LABEL = "Seyamalam v21"
CASES = [(4602 + i, i % 2) for i in range(10)]
OUTPUT = Path("economic_observer_sidecar_fresh10_v0.json")

TERMINAL_DAY = 30
WHEAT_SEED_COST = 10.0
COW_PURCHASE_COST = 400.0
COW_FIRST_YIELD_DAY = 8
COW_YIELD_INTERVAL_DAYS = 2
COW_BASE_UNITS_PER_YIELD = 1.0
SEED_EXPECTED_WHEAT_YIELD_UNITS = 4.0
SEED_HARVEST_DAY = 4


def configure_current():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def _price(obs, item, fallback):
    prices = obs.get("market", {}).get("prices", {})
    value = prices.get(item)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def economic_eval(obs):
    day = int(obs.get("day", 0))
    remaining_days = max(0, TERMINAL_DAY - day)

    wheat_price = _price(obs, "WHEAT", 25.0)
    milk_price = _price(obs, "MILK", 160.0)

    # SEED v0.1: one WHEAT seed -> peak unfertilized yield, fixed current-price approximation.
    if remaining_days >= SEED_HARVEST_DAY:
        seed_total_return = SEED_EXPECTED_WHEAT_YIELD_UNITS * wheat_price
        seed_operating = 0.0
        seed_net = seed_total_return - WHEAT_SEED_COST - seed_operating
        seed_ratio = seed_total_return / max(1e-9, WHEAT_SEED_COST + seed_operating)
        seed_class = "回収可能" if seed_net > 0 else "回収不能寄り"
    else:
        seed_total_return = 0.0
        seed_operating = 0.0
        seed_net = -WHEAT_SEED_COST
        seed_ratio = 0.0
        seed_class = "回収不能寄り"

    # COW v0.1: recurring MILK with feed shadow-priced at current WHEAT price.
    first_yield_abs_day = day + COW_FIRST_YIELD_DAY
    if first_yield_abs_day <= TERMINAL_DAY:
        yield_count = ((TERMINAL_DAY - first_yield_abs_day) // COW_YIELD_INTERVAL_DAYS) + 1
    else:
        yield_count = 0
    cow_total_return = yield_count * COW_BASE_UNITS_PER_YIELD * milk_price
    cow_feed_cost = remaining_days * wheat_price
    cow_net = cow_total_return - COW_PURCHASE_COST - cow_feed_cost
    cow_ratio = cow_total_return / max(1e-9, COW_PURCHASE_COST + cow_feed_cost)
    cow_class = "回収可能" if cow_net > 0 else "回収不能寄り"

    models = {
        "SEED": {
            "net_recoverable": seed_net,
            "recovery_ratio": seed_ratio,
            "recovery_class": seed_class,
            "estimated_total_return": seed_total_return,
            "operating_cost": seed_operating,
            "initial_cost": WHEAT_SEED_COST,
        },
        "COW": {
            "net_recoverable": cow_net,
            "recovery_ratio": cow_ratio,
            "recovery_class": cow_class,
            "estimated_total_return": cow_total_return,
            "operating_cost": cow_feed_cost,
            "initial_cost": COW_PURCHASE_COST,
            "yield_count": yield_count,
        },
    }
    best = max(models, key=lambda k: models[k]["net_recoverable"])
    return {
        "day": day,
        "remaining_days": remaining_days,
        "wheat_price": wheat_price,
        "milk_price": milk_price,
        "models": models,
        "economic_best": best,
    }


def classify_actual(action):
    market = (action or {}).get("market", []) or []
    saw_seed = False
    saw_cow = False
    for order in market:
        if not order:
            continue
        kind = order[0]
        if kind == "BUY_SEED":
            saw_seed = True
        elif kind == "BUY_ANIMAL" and len(order) > 1 and order[1] == "COW":
            saw_cow = True

    if saw_seed and not saw_cow:
        return "SEED"
    if saw_cow and not saw_seed:
        return "COW"
    return "OTHER"


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1-seat])
    margin = own - opp
    return {
        "terminal_self": own,
        "terminal_opponent": opp,
        "margin": margin,
        "win_loss": "win" if margin > 0 else "loss" if margin < 0 else "draw",
    }


def play(seed, seat, battle_id):
    configure_current()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    decisions = []
    turn = 0

    def observed(obs):
        nonlocal turn
        econ = economic_eval(obs)
        action = combat.agent(obs)
        actual = classify_actual(action)
        comparable = actual in ("SEED", "COW")
        alignment = None
        if comparable:
            alignment = "ALIGNED" if actual == econ["economic_best"] else "DIVERGED"
        decisions.append({
            "battle_id": battle_id,
            "decision_id": f"{battle_id}-D{turn:03d}",
            "turn": turn,
            "day": int(obs.get("day", 0)),
            "actual_action": actual,
            "economic_best": econ["economic_best"],
            "comparable": comparable,
            "alignment": alignment,
            "external": econ,
        })
        turn += 1
        return action  # unchanged

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    terminal = score(rewards, seat)

    comp = [d for d in decisions if d["comparable"]]
    aligned = sum(d["alignment"] == "ALIGNED" for d in comp)
    diverged = sum(d["alignment"] == "DIVERGED" for d in comp)
    alignment_rate = aligned / len(comp) if comp else None

    return {
        "battle_id": battle_id,
        "seed": seed,
        "seat": seat,
        "opponent": OPPONENT_LABEL,
        **terminal,
        "comparable_decisions": len(comp),
        "aligned": aligned,
        "diverged": diverged,
        "alignment_rate": alignment_rate,
        "decisions": decisions,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs)/len(xs) if xs else None


def main():
    battles = [
        play(seed, seat, f"B{i+1:02d}")
        for i, (seed, seat) in enumerate(CASES)
    ]

    by_terminal = sorted(battles, key=lambda b: b["terminal_self"])
    low = by_terminal[:5]
    high = by_terminal[5:]

    majority_aligned = [
        b for b in battles
        if b["alignment_rate"] is not None and b["alignment_rate"] >= 0.5
    ]
    majority_diverged = [
        b for b in battles
        if b["alignment_rate"] is not None and b["alignment_rate"] < 0.5
    ]

    summary = {
        "battle_count": len(battles),
        "mean_terminal_self": mean_or_none([b["terminal_self"] for b in battles]),
        "mean_alignment_rate": mean_or_none([b["alignment_rate"] for b in battles]),
        "high_terminal_half_avg_alignment": mean_or_none([b["alignment_rate"] for b in high]),
        "low_terminal_half_avg_alignment": mean_or_none([b["alignment_rate"] for b in low]),
        "majority_aligned_battles_mean_terminal": mean_or_none([b["terminal_self"] for b in majority_aligned]),
        "majority_diverged_battles_mean_terminal": mean_or_none([b["terminal_self"] for b in majority_diverged]),
        "majority_aligned_battle_count": len(majority_aligned),
        "majority_diverged_battle_count": len(majority_diverged),
        "total_comparable_decisions": sum(b["comparable_decisions"] for b in battles),
        "total_aligned": sum(b["aligned"] for b in battles),
        "total_diverged": sum(b["diverged"] for b in battles),
        "boundary": "Economic Best is observation only; no policy promotion or action override.",
    }

    payload = {
        "schema": "kaggriculture.economic-observer-sidecar-fresh10.v0",
        "source_model": "Kaggriculture Minimal Economic Simulator v0.1",
        "combat_model_frozen": True,
        "intervention": "none",
        "comparable_scope": ["SEED", "COW"],
        "excluded_from_alignment": ["LAND", "HANDS", "OTHER"],
        "battles": battles,
        "summary": summary,
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    compact = [{
        "battle_id": b["battle_id"],
        "seed": b["seed"],
        "seat": b["seat"],
        "terminal_self": b["terminal_self"],
        "win_loss": b["win_loss"],
        "margin": b["margin"],
        "comparable_decisions": b["comparable_decisions"],
        "aligned": b["aligned"],
        "diverged": b["diverged"],
        "alignment_rate": b["alignment_rate"],
    } for b in battles]
    print("ECONOMIC_OBSERVER_BATTLES " + json.dumps(compact, separators=(",", ":")))
    print("ECONOMIC_OBSERVER_SUMMARY " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
