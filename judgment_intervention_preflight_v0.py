#!/usr/bin/env python3
"""Preflight for Judgment minimal interventions.

Checks whether a concrete intervention creates an actual action difference
against native G17 at the target State before spending a full Battle run.

This does not evaluate Judgment quality.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
import judgment_day16_minimal_intervention_v0 as probe

SEED = 6301
SEAT = 0
TARGET_DAY = 16
OPPONENT = "opponents/seyamalam_v21.py"
OUT = Path("judgment_intervention_preflight_v0.json")


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
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()


def capture_native():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    captured = {}

    def agent(obs):
        action = current.agent(obs)
        day = int(obs.get("day", 0) or 0)
        if day == TARGET_DAY and "obs" not in captured:
            captured["obs"] = copy.deepcopy(obs)
            captured["action"] = copy.deepcopy(action)
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return captured


def replay_variant(mode):
    probe.set_probe_enabled(True)
    probe.set_attribution_enabled(True)
    probe.reset_experiment(mode)

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    captured = {}

    def agent(obs):
        action = probe.agent(obs)
        day = int(obs.get("day", 0) or 0)
        if day == TARGET_DAY and "action" not in captured:
            captured["obs"] = copy.deepcopy(obs)
            captured["action"] = copy.deepcopy(action)
            captured["events"] = probe.get_events()
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return captured


def classify(native_action, variant_action, events):
    distinct = variant_action != native_action
    if distinct:
        return {
            "reachable": True,
            "distinct": True,
            "classification": "battle_eligible",
        }

    if not events:
        return {
            "reachable": False,
            "distinct": False,
            "classification": "reachability_no_target",
        }

    return {
        "reachable": True,
        "distinct": False,
        "classification": "action_realization_duplicate_or_no_effect",
    }


def main():
    native = capture_native()
    variants = {}

    for name, mode in {
        "B_reduce_workload": "B_reduce_workload",
        "C_increase_capacity": "C_increase_capacity",
    }.items():
        row = replay_variant(mode)
        verdict = classify(
            native.get("action"),
            row.get("action"),
            row.get("events", []),
        )
        variants[name] = {
            "native_action": native.get("action"),
            "variant_action": row.get("action"),
            "events": row.get("events", []),
            **verdict,
        }

    result = {
        "schema": "kaggriculture.judgment-intervention-preflight.v0",
        "seed": SEED,
        "target_day": TARGET_DAY,
        "purpose": "Check reachability/distinctness before Battle.",
        "variants": variants,
        "boundary": [
            "Preflight does not evaluate Judgment quality.",
            "No target => Reachability failure, not hypothesis rejection.",
            "Same action after intervention => Action Realization / duplicate, not Selection failure.",
            "Only distinct variants are Battle-eligible.",
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_INTERVENTION_PREFLIGHT_V0 " + json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
