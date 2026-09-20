#!/usr/bin/env python3
"""Flow/Resource Judgment claim -> expected observable -> intervention -> Battle."""

import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
from judgment_capability_v1 import observe_state
from judgment_day8_flow_claim_v0 import (
    CANDIDATES,
    SCOPE_CONTRACT,
    TARGET_DAY,
    apply_candidate,
    new_scope_state,
)

SEED = 6301
SEAT = 0
OPPONENT = "opponents/seyamalam_v21.py"
OUT = Path("judgment_day8_flow_claim_v0.json")


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


def metrics(obs):
    s = observe_state(obs)
    w = s["work_state"]
    c = s["capacity"]
    return {
        "day": s["time"]["day"],
        "money": s["money"]["self"],
        "hands": c["hands"],
        "empty_tiles": c["empty_tiles"],
        "planted_tiles": c["planted_tiles"],
        "harvestable": w["visible_backlog_components"]["harvestable"],
        "unwatered": w["visible_backlog_components"]["unwatered"],
        "weeds": w["visible_backlog_components"]["weeds"],
        "visible_backlog_sum": (
            w["visible_backlog_components"]["harvestable"]
            + w["visible_backlog_components"]["unwatered"]
            + w["visible_backlog_components"]["weeds"]
        ),
    }


def capture_baseline():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    day8_calls = []

    def agent(obs):
        action = current.agent(obs)
        if int(obs.get("day", 0) or 0) == TARGET_DAY:
            day8_calls.append({"obs": copy.deepcopy(obs), "action": copy.deepcopy(action)})
        return action

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return day8_calls, terminal(env)


def find_first_eligible(calls, candidate_id):
    for idx, row in enumerate(calls):
        scope = new_scope_state()
        variant, events = apply_candidate(row["obs"], row["action"], candidate_id, scope)
        if variant != row["action"]:
            return {
                "classification": "battle_eligible",
                "reachable": True,
                "distinct": True,
                "call_index": idx,
                "native_metrics": metrics(row["obs"]),
                "events": events,
            }
    return {
        "classification": "reachability_no_target",
        "reachable": False,
        "distinct": False,
        "call_index": None,
    }


def play_candidate(candidate_id):
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    scope = new_scope_state()
    applied = []
    first_activation_metrics = None
    next_day_metrics = None

    def agent(obs):
        nonlocal first_activation_metrics, next_day_metrics
        day = int(obs.get("day", 0) or 0)
        if first_activation_metrics is not None and next_day_metrics is None and day > TARGET_DAY:
            next_day_metrics = metrics(obs)

        native_action = current.agent(obs)
        revised, events = apply_candidate(obs, native_action, candidate_id, scope)
        if events and first_activation_metrics is None:
            first_activation_metrics = metrics(obs)
            applied.extend(copy.deepcopy(events))
        return revised

    players = [OPPONENT, OPPONENT]
    players[SEAT] = agent
    env.run(players)
    return {
        "terminal": terminal(env),
        "events": applied,
        "activation_metrics": first_activation_metrics,
        "next_day_metrics": next_day_metrics,
        "scope": copy.deepcopy(scope),
    }


def main():
    calls, baseline = capture_baseline()

    preflight = {}
    eligible = []
    for cid, meta in CANDIDATES.items():
        row = find_first_eligible(calls, cid)
        preflight[cid] = {"description": meta["description"], **row}
        if row["classification"] == "battle_eligible":
            eligible.append(cid)

    battles = {}
    for cid in eligible:
        row = play_candidate(cid)
        t = row["terminal"]
        before = row["activation_metrics"] or {}
        after = row["next_day_metrics"] or {}
        intermediate = {
            "hands_delta_next_day": (
                after.get("hands", 0) - before.get("hands", 0)
                if before and after else None
            ),
            "visible_backlog_delta_next_day": (
                after.get("visible_backlog_sum", 0) - before.get("visible_backlog_sum", 0)
                if before and after else None
            ),
            "harvestable_delta_next_day": (
                after.get("harvestable", 0) - before.get("harvestable", 0)
                if before and after else None
            ),
            "unwatered_delta_next_day": (
                after.get("unwatered", 0) - before.get("unwatered", 0)
                if before and after else None
            ),
        }
        battles[cid] = {
            **row,
            "scope_valid": len(row["events"]) == 1 and row["scope"]["activations"] == 1,
            "intermediate_difference": intermediate,
            "self_diff_vs_current": t["self"] - baseline["self"],
            "margin_diff_vs_current": t["margin"] - baseline["margin"],
            "outcome": (
                "improved" if t["self"] > baseline["self"]
                else "worsened" if t["self"] < baseline["self"]
                else "same"
            ),
        }

    payload = {
        "schema": "kaggriculture.judgment-day8-flow-claim.v0",
        "judgment_claim": (
            "Visible flow blockage may justify recover-oriented realizations before "
            "committing to cash/expansion direction."
        ),
        "expected_observable_change": [
            "visible backlog components improve or grow more slowly",
            "capacity realization may increase hands",
        ],
        "scope_contract": SCOPE_CONTRACT,
        "baseline": baseline,
        "preflight": preflight,
        "battle_eligible": eligible,
        "battles": battles,
        "interpretation_labels": [
            "supported",
            "contradicted",
            "unresolved",
            "invalid realization",
        ],
        "boundary": [
            "Do not infer Judgment quality from terminal score alone.",
            "First inspect the expected observable change.",
            "Concrete intervention failure does not automatically reject the abstract Claim.",
            "No pipeline modification is attempted in this run.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_DAY8_FLOW_CLAIM_V0 " + json.dumps({
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
        "battles": {
            cid: {
                "scope_valid": row["scope_valid"],
                "intermediate_difference": row["intermediate_difference"],
                "self_diff_vs_current": row["self_diff_vs_current"],
                "margin_diff_vs_current": row["margin_diff_vs_current"],
                "outcome": row["outcome"],
            }
            for cid, row in battles.items()
        },
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
