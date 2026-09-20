#!/usr/bin/env python3
"""Batch Preflight -> minimal Battle for Day16 Judgment claim.

1. Capture one native Day16 State/action.
2. Apply every concrete candidate offline.
3. Hold unreachable/duplicate candidates.
4. Battle only candidates that create a distinct action.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
from judgment_day16_intervention_batch_v0 import CANDIDATES, TARGET_DAY, apply_candidate

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
    applied = []

    def agent(obs):
        native_action = current.agent(obs)
        revised, events = apply_candidate(obs, native_action, candidate_id)
        if events:
            applied.extend(copy.deepcopy(events))
        return revised

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return terminal(env), applied


def main():
    captured, baseline = capture_baseline()
    native_action = captured["action"]
    obs = captured["obs"]

    preflight = {}
    eligible = []
    for cid, meta in CANDIDATES.items():
        variant_action, events = apply_candidate(obs, native_action, cid)
        classification = classify(native_action, variant_action, events)
        preflight[cid] = {
            "facet": meta["facet"],
            "description": meta["description"],
            "classification": classification,
            "reachable": bool(events),
            "distinct": variant_action != native_action,
            "events": events,
            "variant_action": variant_action,
        }
        if classification == "battle_eligible":
            eligible.append(cid)

    battles = {}
    for cid in eligible:
        result, events = play_candidate(cid)
        battles[cid] = {
            **result,
            "events": events,
            "self_diff_vs_current": result["self"] - baseline["self"],
            "margin_diff_vs_current": result["margin"] - baseline["margin"],
            "outcome": (
                "improved" if result["self"] > baseline["self"]
                else "worsened" if result["self"] < baseline["self"]
                else "same"
            ),
        }

    payload = {
        "schema": "kaggriculture.judgment-day16-batch-preflight-battle.v0",
        "judgment_claim": (
            "recover may have multiple realizations: reduce incoming workload, "
            "increase work capacity, or reprioritize existing work"
        ),
        "baseline": baseline,
        "preflight": preflight,
        "battle_eligible": eligible,
        "battles": battles,
        "boundary": [
            "Preflight judges only reachability/distinctness, never action quality.",
            "Unreachable or duplicate candidates are held, not treated as Judgment rejection.",
            "Battle result evaluates the concrete intervention only.",
            "One seed does not establish the abstract Judgment claim.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_DAY16_BATCH_V0 " + json.dumps({
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
