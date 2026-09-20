#!/usr/bin/env python3
"""Generate one previously-unlabeled Battle and package it for Open Learning Probe v0."""

import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state
from open_learning_probe_v0 import build_open_learning_packet

SEED = 6201
SEAT = 0
OPPONENT = base.OPPONENT
OPPONENT_LABEL = "Seyamalam v21"
OUT = Path("open_learning_probe_v0.json")


def configure_current_model():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()


def play_unknown_battle():
    configure_current_model()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    daily = []
    last_day = None

    def observed_agent(obs):
        nonlocal last_day
        day = int(obs.get("day", 0) or 0)
        snapshot = observe_state(obs)
        if day != last_day:
            daily.append(snapshot)
            last_day = day
        else:
            daily[-1] = snapshot
        return combat.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed_agent
    env.run(players)

    rewards = [float(state.reward) for state in env.state]
    own = rewards[SEAT]
    opp = rewards[1 - SEAT]
    margin = own - opp

    return {
        "case_identity": {
            "seed": SEED,
            "seat": SEAT,
            "opponent": OPPONENT_LABEL,
            "previous_learning_label": None,
            "purpose": "unknown-case open learning observation",
        },
        "terminal": {
            "self": own,
            "opponent": opp,
            "margin": margin,
            "win_loss": "win" if margin > 0 else "loss" if margin < 0 else "draw",
        },
        "daily_observed_state": daily,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }


def main():
    battle = play_unknown_battle()
    packet = build_open_learning_packet(battle)
    OUT.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("OPEN_LEARNING_DAILY_STATE " + json.dumps([
        {
            "day": s["time"]["day"],
            "remaining": s["time"]["remaining_days"],
            "money": s["money"],
            "capacity": s["capacity"],
            "flow_inputs": s["flow_inputs"],
            "flow_outputs": s["flow_outputs"],
            "work_state": s["work_state"],
        }
        for s in battle["daily_observed_state"]
    ], ensure_ascii=False, separators=(",", ":")))

    print("OPEN_LEARNING_PROBE_V0 " + json.dumps({
        "case": battle["case_identity"],
        "terminal": battle["terminal"],
        "daily_observations": len(battle["daily_observed_state"]),
        "boundary": packet["learning_boundary"],
        "taxonomy": packet["reference_taxonomy"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
