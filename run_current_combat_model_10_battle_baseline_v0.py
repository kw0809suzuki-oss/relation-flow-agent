#!/usr/bin/env python3
"""Current Combat Model — 10 Battle Baseline v0.

Battle-first outer observation only.

Freeze:
- current Combat Model unchanged
- no candidate rule
- no new gate
- no internal trace analysis
- no causal interpretation

Record per battle:
seed / seat / opponent / terminal self / terminal opponent / margin /
win-loss / run reference.
"""

import json
import os
import statistics
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

OPPONENT = base.OPPONENT
OPPONENT_LABEL = "Seyamalam v21"
CASES = [(4602 + i, i % 2) for i in range(10)]
OUTPUT = Path("current_combat_model_10_battle_baseline_v0.json")


def configure_current_model():
    # Keep exactly the same current baseline identity used by recent Battles.
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def play(seed, seat):
    configure_current_model()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = combat.agent
    env.run(players)

    rewards = [float(state.reward) for state in env.state]
    own = rewards[seat]
    opp = rewards[1 - seat]
    margin = own - opp
    result = "win" if margin > 0 else "loss" if margin < 0 else "draw"

    return {
        "seed": seed,
        "seat": seat,
        "opponent": OPPONENT_LABEL,
        "terminal_self": own,
        "terminal_opponent": opp,
        "margin": margin,
        "win_loss": result,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "artifact_name": "current-combat-model-10-battle-baseline-v0",
    }


def main():
    rows = [play(seed, seat) for seed, seat in CASES]

    self_values = [r["terminal_self"] for r in rows]
    margins = [r["margin"] for r in rows]
    wins = sum(r["win_loss"] == "win" for r in rows)
    losses = sum(r["win_loss"] == "loss" for r in rows)
    draws = sum(r["win_loss"] == "draw" for r in rows)

    min_row = min(rows, key=lambda r: r["terminal_self"])
    max_row = max(rows, key=lambda r: r["terminal_self"])

    summary = {
        "battle_count": len(rows),
        "mean_self": sum(self_values) / len(self_values),
        "median_self": statistics.median(self_values),
        "min_self": min(self_values),
        "max_self": max(self_values),
        "mean_margin": sum(margins) / len(margins),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": wins / len(rows),
        "largest_accident": {
            "seed": min_row["seed"],
            "seat": min_row["seat"],
            "terminal_self": min_row["terminal_self"],
            "margin": min_row["margin"],
        },
        "highest_self": {
            "seed": max_row["seed"],
            "seat": max_row["seat"],
            "terminal_self": max_row["terminal_self"],
            "margin": max_row["margin"],
        },
    }

    payload = {
        "schema": "kaggriculture.current-combat-model-10-battle-baseline.v0",
        "purpose": "outer-shape observation of the unchanged current Combat Model",
        "combat_model_frozen": True,
        "combat_model_identity": "recent Battle baseline: export_scale_baseline_v1 configuration; whole_flow_control disabled; Bundle Flow env enabled",
        "opponent_scope": "single fixed opponent in this baseline; opponent-bias comparison is not inferred",
        "analysis_boundary": "No new Rule/Gate/theory or cause analysis during these 10 battles.",
        "battles": rows,
        "summary": summary,
    }

    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("CURRENT_COMBAT_MODEL_10_BATTLE_ROWS " + json.dumps(rows, separators=(",", ":")))
    print("CURRENT_COMBAT_MODEL_10_BATTLE_SUMMARY " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
