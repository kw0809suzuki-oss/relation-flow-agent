#!/usr/bin/env python3
"""Observe Production Agent v1 with a result-blind production Bundle.

Bundle is frozen before terminal rewards are read. It is used only to compare
capacity, queue state, market state and action throughput across matches/days.
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make

import production_bundle_observer as observer

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3862) % 2) for seed in range(3862, 3874))


def play(seed, seat):
    observer.reset()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = observer.agent
    env.run(players)
    bundle = observer.get_bundle()  # freeze before terminal
    rewards = [state.reward for state in env.state]
    terminal = {
        "self": float(rewards[seat]),
        "opponent": float(rewards[1-seat]),
        "margin": float(rewards[seat]) - float(rewards[1-seat]),
        "win": float(rewards[seat]) > float(rewards[1-seat]),
    }
    return {"seed": seed, "seat": seat, "bundle": bundle, "terminal": terminal}


def mean(xs):
    return statistics.mean(xs) if xs else 0.0


def aggregate(cases):
    by_day = defaultdict(list)
    for case in cases:
        for d in case["bundle"]["days"]:
            by_day[d["day"]].append(d)

    daily = []
    for day in sorted(by_day):
        rows = by_day[day]
        def vals(fn): return [fn(r) for r in rows]
        daily.append({
            "day": day,
            "cases": len(rows),
            "self_minus_opponent": {
                "money": mean(vals(lambda r: r["snapshot"]["self"]["money"] - r["snapshot"]["opponent"]["money"])),
                "hands": mean(vals(lambda r: r["snapshot"]["self"]["hands"] - r["snapshot"]["opponent"]["hands"])),
                "land": mean(vals(lambda r: r["snapshot"]["self"]["land"] - r["snapshot"]["opponent"]["land"])),
                "active_tiles": mean(vals(lambda r: r["snapshot"]["self"]["active_tiles"] - r["snapshot"]["opponent"]["active_tiles"])),
                "animals": mean(vals(lambda r: r["snapshot"]["self"]["animal_total"] - r["snapshot"]["opponent"]["animal_total"])),
            },
            "self_queue_mean": {
                "wheat": mean(vals(lambda r: r["snapshot"]["self_private"]["wheat"])),
                "unfed_cows": mean(vals(lambda r: r["snapshot"]["self_private"]["unfed_cows"])),
                "care_wait_cows": mean(vals(lambda r: r["snapshot"]["self_private"]["care_wait_cows"])),
                "harvest_ready_cows": mean(vals(lambda r: r["snapshot"]["self_private"]["harvest_ready_cows"])),
                "produce_inventory": mean(vals(lambda r: r["snapshot"]["self_private"]["produce_inventory"])),
            },
            "action_mean": {
                k: mean([r["actions"].get(k, 0) for r in rows])
                for k in ("move", "work", "feed", "care", "harvest", "drop", "sell_order", "buy_wheat", "buy_animal", "hire", "buy_land")
            },
        })

    queue_metrics = ("unfed_cows", "care_wait_cows", "harvest_ready_cows", "produce_inventory")
    queue_peaks = {}
    for metric in queue_metrics:
        ranked = sorted(
            ({"day": d["day"], "mean": d["self_queue_mean"][metric]} for d in daily),
            key=lambda x: x["mean"], reverse=True,
        )[:5]
        queue_peaks[metric] = ranked

    public_gap_extremes = {}
    for metric in ("money", "hands", "land", "active_tiles", "animals"):
        ranked = sorted(
            ({"day": d["day"], "self_minus_opponent": d["self_minus_opponent"][metric]} for d in daily),
            key=lambda x: x["self_minus_opponent"],
        )[:5]
        public_gap_extremes[metric] = ranked

    return {"daily_comparison": daily, "queue_peaks": queue_peaks, "public_gap_extremes": public_gap_extremes}


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    comparison = aggregate(cases)
    out = {
        "schema": "kaggriculture.production-bundle-observation.v1",
        "front": "Production Agent v1",
        "back": "observation-only production Bundle",
        "cases": cases,
        "comparison": comparison,
        "summary": {
            "case_count": len(cases),
            "wins": sum(c["terminal"]["win"] for c in cases),
            "mean_self": mean([c["terminal"]["self"] for c in cases]),
            "mean_margin": mean([c["terminal"]["margin"] for c in cases]),
            "all_bundles_result_blind": all(c["bundle"]["constructed_without_terminal"] for c in cases),
        },
        "boundary": {
            "bundle_used_for_control": False,
            "terminal_used_to_construct_bundle": False,
            "causal_attribution": False,
            "comparison_only": True,
        },
    }
    Path("production_bundle_observation_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    compact = {
        "summary": out["summary"],
        "queue_peaks": comparison["queue_peaks"],
        "public_gap_extremes": comparison["public_gap_extremes"],
    }
    print("PRODUCTION_BUNDLE_OBSERVATION " + json.dumps(compact, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
