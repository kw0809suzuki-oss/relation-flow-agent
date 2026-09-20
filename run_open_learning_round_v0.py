#!/usr/bin/env python3
"""Generate one fresh Open Learning Round from an unknown Battle."""

import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state
from open_learning_round_v0 import build_open_learning_round

SEED = 6204
SEAT = 1
OPPONENT = base.OPPONENT
OPPONENT_LABEL = "Seyamalam v21"
OUT = Path("open_learning_round_v0.json")

OPEN_CANDIDATES = [
    {
        "candidate": "temporal_realization",
        "maturity": "replicated",
        "adoption": "proposed",
        "formal_taxonomy_member": False,
        "working_description": (
            "A value-producing action sequence may execute locally yet fail to convert its "
            "remaining investment into terminal value within the available horizon."
        ),
    }
]


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def play():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    daily = []
    last_day = None

    def agent(obs):
        nonlocal last_day
        day = int(obs.get("day", 0) or 0)
        state = observe_state(obs)
        if day != last_day:
            daily.append(state)
            last_day = day
        else:
            daily[-1] = state
        return combat.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)

    rewards = [float(x.reward) for x in env.state]
    battle = {
        "case_identity": {
            "seed": SEED,
            "seat": SEAT,
            "opponent": OPPONENT_LABEL,
            "previous_learning_label": None,
            "purpose": "unknown Battle candidate competition",
        },
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1-SEAT],
            "margin": rewards[SEAT] - rewards[1-SEAT],
            "win_loss": "win" if rewards[SEAT] > rewards[1-SEAT] else "loss" if rewards[SEAT] < rewards[1-SEAT] else "draw",
        },
        "daily_observed_state": daily,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    return battle


def main():
    battle = play()
    packet = build_open_learning_round(battle, OPEN_CANDIDATES)
    OUT.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("OPEN_LEARNING_ROUND_V0 " + json.dumps({
        "case": battle["case_identity"],
        "terminal": battle["terminal"],
        "daily_observations": len(battle["daily_observed_state"]),
        "candidate_pool": packet["candidate_pool"],
        "learning_boundary": packet["learning_boundary"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
