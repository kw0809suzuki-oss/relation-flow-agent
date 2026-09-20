#!/usr/bin/env python3
"""Single-shot Day16 Judgment bridge.

Reuses the same three concrete interventions from the previous batch.
Only intervention scope is changed to one activation.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
from judgment_day16_intervention_batch_v0 import (
    CANDIDATES,
    SCOPE_CONTRACT,
    TARGET_DAY,
    apply_candidate,
    new_scope_state,
)

SEED = 6301
SEAT = 0
OPPONENT = "opponents/seyamalam_v21.py"
OUT = Path("judgment_day16_batch_preflight_battle_v0.json")


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


def terminal(env):
    rewards = [float(s.reward) for s in env.state]
    return {
        "self": rewards[SEAT],
        "opponent": rewards[1-SEAT],
        "margin": rewards[SEAT] - rewards[1-SEAT],
        "win": rewards[SEAT] > rewards[1-SEAT],
    }


def capture_baseline():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    captured = {}

    def agent(obs):
        action = current.agent(obs)
        if int(obs.get("day", 0) or 0) == TARGET_DAY and "obs" not in captured:
            captured["obs"] = copy.deepcopy(obs)
            captured["action"] = copy.deepcopy(action)
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return captured, terminal(env)


def classify(native_action, variant_action, events):
    if variant_action != native_action:
        return "battle_eligible"
    if not events:
        return "reachability_no_target"
    return "action_realization_duplicate_or_no_effect"


def play_candidate(candidate_id):
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    scope = new_scope_state()
    applied = []

    def agent(obs):
        native_action = current.agent(obs)
        revised, events = apply_candidate(obs, native_action, candidate_id, scope)
        if events:
            applied.extend(copy.deepcopy(events))
        return revised

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return terminal(env), applied, copy.deepcopy(scope)


def main():
    captured, baseline = capture_baseline()
    native_action = captured["action"]
    obs = captured["obs"]

    preflight = {}
    eligible = []
    for cid, meta in CANDIDATES.items():
        scope = new_scope_state()
        variant_action, events = apply_candidate(obs, native_action, cid, scope)
        classification = classify(native_action, variant_action, events)
        preflight[cid] = {
            "facet": meta["facet"],
            "description": meta["description"],
            "classification": classification,
            "reachable": bool(events),
            "distinct": variant_action != native_action,
            "scope_after_preflight": scope,
            "events": events,
        }
        if classification == "battle_eligible":
            eligible.append(cid)

    battles = {}
    for cid in eligible:
        result, events, scope = play_candidate(cid)
        battles[cid] = {
            **result,
            "events": events,
            "activation_count": len(events),
            "scope_final": scope,
            "scope_valid": len(events) == 1 and scope.get("activations") == 1,
            "self_diff_vs_current": result["self"] - baseline["self"],
            "margin_diff_vs_current": result["margin"] - baseline["margin"],
            "outcome": (
                "improved" if result["self"] > baseline["self"]
                else "worsened" if result["self"] < baseline["self"]
                else "same"
            ),
        }

    payload = {
        "schema": "kaggriculture.judgment-day16-single-shot.v0.1",
        "judgment_claim": (
            "recover may have multiple realizations: reduce workload or increase work capacity"
        ),
        "scope_contract": SCOPE_CONTRACT,
        "baseline": baseline,
        "preflight": preflight,
        "battle_eligible": eligible,
        "battles": battles,
        "boundary": [
            "Only intervention scope changed from the previous run.",
            "Preflight judges reachability/distinctness only.",
            "Battle result evaluates the concrete intervention, not the abstract Judgment claim.",
            "Scope must be valid before using the Battle result for Judgment analysis.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_DAY16_SINGLE_SHOT_V01 " + json.dumps({
        "scope_contract": SCOPE_CONTRACT,
        "baseline": baseline,
        "preflight": {
            cid: {
                "classification": row["classification"],
                "reachable": row["reachable"],
                "distinct": row["distinct"],
            }
            for cid, row in preflight.items()
        },
        "battle_eligible": eligible,
        "battles": battles,
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
