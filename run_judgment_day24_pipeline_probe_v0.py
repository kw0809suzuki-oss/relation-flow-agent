#!/usr/bin/env python3
"""Reuse the Judgment pipeline on a different conflict: Day24 closure vs short-grow."""

import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
from judgment_day24_intervention_batch_v0 import (
    CANDIDATES,
    SCOPE_CONTRACT,
    TARGET_DAY,
    apply_candidate,
    new_scope_state,
)

SEED = 6301
SEAT = 0
OPPONENT = "opponents/seyamalam_v21.py"
OUT = Path("judgment_day24_pipeline_probe_v0.json")


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
    calls = []

    def agent(obs):
        action = current.agent(obs)
        if int(obs.get("day", 0) or 0) == TARGET_DAY:
            calls.append({"obs": copy.deepcopy(obs), "action": copy.deepcopy(action)})
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return calls, terminal(env)


def find_first_eligible(calls, candidate_id):
    for idx, row in enumerate(calls):
        scope = new_scope_state()
        variant, events = apply_candidate(row["obs"], row["action"], candidate_id, scope)
        if variant != row["action"]:
            return {
                "call_index": idx,
                "obs": row["obs"],
                "native_action": row["action"],
                "variant_action": variant,
                "events": events,
                "classification": "battle_eligible",
                "reachable": True,
                "distinct": True,
            }
    return {
        "classification": "reachability_no_target",
        "reachable": False,
        "distinct": False,
    }


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
    return terminal(env), applied, scope


def main():
    calls, baseline = capture_baseline()

    preflight = {}
    eligible = []
    for cid, meta in CANDIDATES.items():
        row = find_first_eligible(calls, cid)
        preflight[cid] = {
            "description": meta["description"],
            **row,
        }
        if row["classification"] == "battle_eligible":
            eligible.append(cid)

    battles = {}
    for cid in eligible:
        result, events, scope = play_candidate(cid)
        battles[cid] = {
            **result,
            "events": events,
            "activation_count": len(events),
            "scope_valid": len(events) == 1 and scope["activations"] == 1 and scope["closed"],
            "self_diff_vs_current": result["self"] - baseline["self"],
            "margin_diff_vs_current": result["margin"] - baseline["margin"],
            "outcome": (
                "improved" if result["self"] > baseline["self"]
                else "worsened" if result["self"] < baseline["self"]
                else "same"
            ),
        }

    payload = {
        "schema": "kaggriculture.judgment-day24-pipeline-probe.v0",
        "conflict": "closure-oriented hold-all vs short-grow-preserving hold-long-assets",
        "scope_contract": SCOPE_CONTRACT,
        "baseline": baseline,
        "preflight": preflight,
        "battle_eligible": eligible,
        "battles": battles,
        "boundary": [
            "Same pipeline as Day16; no new decision machinery.",
            "Preflight judges reachability/distinctness only.",
            "Single-shot scope must be valid before reading Battle differences.",
            "Concrete result does not directly prove the abstract Judgment relation.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_DAY24_PIPELINE_V0 " + json.dumps({
        "baseline": baseline,
        "preflight": {
            cid: {
                "classification": row["classification"],
                "reachable": row["reachable"],
                "distinct": row["distinct"],
                "call_index": row.get("call_index"),
            }
            for cid, row in preflight.items()
        },
        "battle_eligible": eligible,
        "battles": battles,
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
