#!/usr/bin/env python3
"""Strength Benchmark v0 shadow snapshot for the frozen D14 candidate.

This is NOT SB-01 and does not record Strength Progress.
It reuses the exact Strength Benchmark v0 seed/seat/opponent/runtime path,
then applies the frozen D14 market filter after the current Combat Model action.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OPPONENT = base.OPPONENT
OUT = Path(f"d14_strength_benchmark_v0_shadow_{SEED}.json")
START_DAY = 14

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def is_expansion(order):
    if not isinstance(order, (list, tuple)) or not order:
        return False
    op = order[0]
    if op in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(order) > 1 and order[1] == "COW"

def play():
    configure()
    activation_count = 0
    removed_orders = 0
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)

    def candidate(obs):
        nonlocal activation_count, removed_orders
        actions = combat.agent(obs)
        if not isinstance(actions, dict):
            return actions
        day = int(obs.get("day", 0) or 0)
        if day < START_DAY:
            return actions
        market = list(actions.get("market", []) or [])
        removed = [a for a in market if is_expansion(a)]
        if not removed:
            return actions
        revised = copy.deepcopy(actions)
        revised["market"] = [a for a in market if not is_expansion(a)]
        activation_count += 1
        removed_orders += len(removed)
        return revised

    players = [OPPONENT, OPPONENT]
    players[SEAT] = candidate
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    terminal_self = rewards[SEAT]
    terminal_opponent = rewards[1-SEAT]
    terminal_margin = terminal_self - terminal_opponent
    outcome = "win" if terminal_margin > 0 else "loss" if terminal_margin < 0 else "draw"
    return {
        "terminal_self": terminal_self,
        "terminal_opponent": terminal_opponent,
        "terminal_margin": terminal_margin,
        "outcome": outcome,
        "activation_count": activation_count,
        "removed_orders": removed_orders,
    }

def main():
    result = play()
    payload = {
        "schema": "kaggriculture.strength-benchmark.v0.d14-shadow",
        "benchmark": "strength_benchmark_v0",
        "snapshot": "D14-SHADOW-00",
        "status": "provisional_unadopted_candidate",
        "seed": SEED,
        "seat": SEAT,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "commit": os.environ.get("GITHUB_SHA"),
        **result,
        "boundary": [
            "Uses the fixed Strength Benchmark v0 seeds 7001-7050 and alternating seats.",
            "Uses the same opponent and current Combat Model runtime path as SB-00.",
            "Applies only the frozen D14 late-expansion filter after the Combat Model action.",
            "This is a shadow snapshot for an unadopted candidate, not SB-01.",
            "A favorable result does not establish Strength Progress or adoption."
        ]
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("D14_STRENGTH_BENCHMARK_V0_SHADOW " + json.dumps(payload, ensure_ascii=False, separators=(",",":")))

if __name__ == "__main__":
    main()
