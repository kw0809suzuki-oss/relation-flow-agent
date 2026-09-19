#!/usr/bin/env python3
"""Bundle Battle v0: M0/M2/M3/M4/M6/M7 × same fresh5.

Goal: observe external design-space response, not rank a winner.
No internal trace analysis.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import bundle_variants_v0 as bundle

OPPONENT = base.OPPONENT
OPPONENT_LABEL = "Seyamalam v21"
CASES = [(5301 + i, i % 2) for i in range(5)]
MODELS = ["M0", "M2", "M3", "M4", "M6", "M7"]
OUTPUT = Path("bundle_battle_fresh5_v0.json")

def configure():
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    bundle.set_probe_enabled(True)
    bundle.set_attribution_enabled(True)
    bundle.reset_experiment()

def _price(obs, item, fallback):
    try:
        return float((obs.get("market", {}).get("prices", {}) or {}).get(item, fallback))
    except Exception:
        return float(fallback)

def _private_total(obs, item):
    p = obs.get("private", {}) or {}
    shed = p.get("shed", {}) or {}
    inventories = p.get("inventories", []) or []
    return float(shed.get(item, 0) or 0) + sum(float((x or {}).get(item, 0) or 0) for x in inventories)

def _terminal_inventory_mark(last_obs):
    if not last_obs:
        return None
    # Observable inventory-only mark-to-market. Does not assign liquidation value
    # to LAND/HANDS/animals because no grounded terminal liquidation rule exists.
    items = ["WHEAT", "MILK", "WOOL", "EGG", "FERTILIZER"]
    total = 0.0
    for item in items:
        total += _private_total(last_obs, item) * _price(last_obs, item, 0.0)
    return total

def play(model, seed, seat):
    configure()
    bundle.set_variant(model)
    last_obs = {"value": None}

    def wrapped(obs):
        last_obs["value"] = obs
        return bundle.agent(obs)

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = wrapped
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    acts = bundle.get_activations()

    return {
        "model": model,
        "seed": seed,
        "seat": seat,
        "self": rewards[seat],
        "opp": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
        "win_loss": "win" if rewards[seat] > rewards[1-seat] else "loss" if rewards[seat] < rewards[1-seat] else "draw",
        "activation_count": len(acts),
        "activation_days": sorted({a["day"] for a in acts}),
        "terminal_inventory_mark_to_market": _terminal_inventory_mark(last_obs["value"]),
    }

def mean(xs):
    return sum(xs) / len(xs) if xs else None

def main():
    rows = []
    for model in MODELS:
        for seed, seat in CASES:
            rows.append(play(model, seed, seat))

    by_model = {}
    current = {(r["seed"], r["seat"]): r for r in rows if r["model"] == "M0"}

    for model in MODELS:
        rs = [r for r in rows if r["model"] == model]
        diffs = [
            r["self"] - current[(r["seed"], r["seat"])]["self"]
            for r in rs
        ]
        by_model[model] = {
            "battle_count": len(rs),
            "mean_self": mean([r["self"] for r in rs]),
            "mean_margin": mean([r["margin"] for r in rs]),
            "wins": sum(r["win_loss"] == "win" for r in rs),
            "losses": sum(r["win_loss"] == "loss" for r in rs),
            "activated_cases": sum(r["activation_count"] > 0 for r in rs),
            "activation_count": sum(r["activation_count"] for r in rs),
            "mean_self_diff_vs_current": mean(diffs),
            "improved_vs_current": sum(d > 0 for d in diffs),
            "worsened_vs_current": sum(d < 0 for d in diffs),
            "equal_vs_current": sum(d == 0 for d in diffs),
            "mean_terminal_inventory_mark_to_market": mean([
                r["terminal_inventory_mark_to_market"] for r in rs
                if r["terminal_inventory_mark_to_market"] is not None
            ]),
        }

    payload = {
        "schema": "kaggriculture.bundle-battle-fresh5.v0",
        "objective": "terminal self money / win rate; external design-space observation",
        "models": MODELS,
        "cases": CASES,
        "opponent": OPPONENT_LABEL,
        "variant_definitions": {
            "M0": "Current G17 unchanged",
            "M2": "Day20+: suppress all new expansion purchases",
            "M3": "Day26+: suppress all new expansion purchases",
            "M4": "time-weighted cash reserve; reserve fraction rises linearly with day",
            "M6": "recovery-first: SEED requires >=4 days; COW >=8 days; LAND untouched",
            "M7": "staged switch: Day20+ suppress LAND/COW; Day26+ suppress all expansion",
        },
        "boundary": [
            "No model is adopted from fresh5.",
            "This is design-space mapping, not a winner ranking.",
            "terminal_inventory_mark_to_market covers observable inventory only; no fake liquidation value for LAND/HANDS/animals.",
        ],
        "rows": rows,
        "summary_by_model": by_model,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BUNDLE_BATTLE_SUMMARY " + json.dumps(by_model, ensure_ascii=False, separators=(",", ":")))
    print("BUNDLE_BATTLE_ROWS " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
