#!/usr/bin/env python3
"""Closure Receiver Final Separator Audit.

One operation only. Discovery on the completed fresh40 population.
Uses only pre-action, already-available state at the first baseline/candidate
Action divergence. Searches only one-feature / one-threshold gates.

This audit cannot promote or adopt a rule. If one separator passes the
pre-registered criteria, it becomes at most one frozen candidate for an
independent unseen-seed Battle.
"""

import copy
import json
import math
import os
from pathlib import Path
from statistics import mean, median

from kaggle_environments import make
import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((4902 + i, i % 2) for i in range(40))
GAIN = 0.60
LARGE_LOSS = -5000.0
MIN_SUPPORT = 10

# No seat, receiver output, Action-difference count, or terminal-derived feature.
FEATURES = (
    "day",
    "remaining",
    "money",
    "units",
    "land",
    "cows",
    "wheat",
    "feed_need",
    "feed_shortfall",
    "outputs",
)


def configure(abstraction=None, gain=None):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    if abstraction is None:
        os.environ.pop("G15_STRATEGY_ABSTRACTION", None)
        os.environ.pop("G15_OPTION_PRESERVING_GAIN", None)
    else:
        os.environ["G15_STRATEGY_ABSTRACTION"] = abstraction
        os.environ["G15_OPTION_PRESERVING_GAIN"] = str(gain)
    agent.set_control_enabled(True)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def econ_state(obs):
    player = int(obs["player"])
    me = obs["farms"][player]
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []

    def total(item):
        return shed.get(item, 0) + sum((inv or {}).get(item, 0) for inv in inventories)

    cows = total("COW")
    for row in me.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                cows += 1

    outputs = sum(total(k) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
    return {
        "day": obs.get("day"),
        "hour": obs.get("hour"),
        "money": float(me.get("money", 0)),
        "units": 1 + len(me.get("hands", [])),
        "land": len(me.get("unlocked_quadrants", [])),
        "cows": cows,
        "wheat": total("WHEAT"),
        "outputs": outputs,
    }


def play(seed, seat, abstraction=None, gain=None):
    configure(abstraction, gain)
    actions, states = [], []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        states.append(econ_state(obs))
        action = agent.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [float(state.reward) for state in env.state]
    return {
        "self": rewards[seat],
        "opponent": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
        "actions": actions,
        "states": states,
        "trace": agent.get_trace(),
    }


def first_difference(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    return min(len(left), len(right)) if len(left) != len(right) else None


def snapshot_at(trace, index):
    try:
        snaps = trace["body"]["observe"]["body"]["snapshots"]
        return snaps[index] if 0 <= index < len(snaps) else {}
    except Exception:
        return {}


def summarize_deltas(deltas):
    return {
        "count": len(deltas),
        "improved": sum(x > 0 for x in deltas),
        "worsened": sum(x < 0 for x in deltas),
        "equal": sum(x == 0 for x in deltas),
        "mean": mean(deltas) if deltas else 0.0,
        "median": median(deltas) if deltas else 0.0,
        "min": min(deltas) if deltas else 0.0,
        "max": max(deltas) if deltas else 0.0,
        "large_loss_count": sum(x <= LARGE_LOSS for x in deltas),
    }


def thresholds(values):
    vals = sorted(set(float(v) for v in values if v is not None and math.isfinite(float(v))))
    if len(vals) < 2:
        return []
    # Midpoints separate observed values without equality ambiguity.
    return [(a + b) / 2.0 for a, b in zip(vals, vals[1:]) if a != b]


def audit_gate(rows, feature, op, threshold):
    if op == ">=":
        enabled = [r for r in rows if r["state"][feature] >= threshold]
    else:
        enabled = [r for r in rows if r["state"][feature] <= threshold]
    disabled = [r for r in rows if r not in enabled]
    deltas = [r["self_diff"] for r in enabled]
    summary = summarize_deltas(deltas)
    conditional_all40 = [r["self_diff"] if r in enabled else 0.0 for r in rows]
    conditional_summary = summarize_deltas(conditional_all40)

    passes = (
        len(enabled) >= MIN_SUPPORT
        and summary["mean"] > 0
        and summary["improved"] > summary["worsened"]
        and summary["large_loss_count"] == 0
        and conditional_summary["mean"] > 0
    )

    return {
        "feature": feature,
        "operator": op,
        "threshold": threshold,
        "support": len(enabled),
        "excluded": len(disabled),
        "enabled_terminal_self": summary,
        "conditional_all40_self": conditional_summary,
        "passes": passes,
    }


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat)
        candidate = play(seed, seat, "option_preserving", GAIN)
        idx = first_difference(baseline["actions"], candidate["actions"])
        if idx is None:
            raise RuntimeError(f"no Action difference for seed={seed} seat={seat}")

        base_state = dict(baseline["states"][idx])
        cand_state = dict(candidate["states"][idx])
        if base_state != cand_state:
            raise RuntimeError(f"state mismatch before first Action difference seed={seed} seat={seat}")

        base_snap = snapshot_at(baseline["trace"], idx)
        cand_snap = snapshot_at(candidate["trace"], idx)
        for key in ("money", "units", "land", "cows", "wheat", "day"):
            if base_snap.get(key) != cand_snap.get(key):
                raise RuntimeError(f"snapshot state mismatch {key} seed={seed} seat={seat}")

        state = {
            "day": float(base_state["day"]),
            "remaining": float(base_snap.get("remaining", 0)),
            "money": float(base_state["money"]),
            "units": float(base_state["units"]),
            "land": float(base_state["land"]),
            "cows": float(base_state["cows"]),
            "wheat": float(base_state["wheat"]),
            "feed_need": float(base_snap.get("feed_need", 0) or 0),
            "outputs": float(base_state["outputs"]),
        }
        state["feed_shortfall"] = max(0.0, state["feed_need"] - state["wheat"])

        row = {
            "seed": seed,
            "seat": seat,
            "first_action_difference": idx,
            "self_diff": candidate["self"] - baseline["self"],
            "margin_diff": candidate["margin"] - baseline["margin"],
            "state": state,
            "pre_action_state_equal": True,
        }
        rows.append(row)
        print("AUDIT_CASE " + json.dumps(row, separators=(",", ":")))

    observed_self = [r["self_diff"] for r in rows]
    observed_summary = summarize_deltas(observed_self)

    candidates = []
    for feature in FEATURES:
        vals = [r["state"][feature] for r in rows]
        for threshold in thresholds(vals):
            for op in (">=", "<="):
                result = audit_gate(rows, feature, op, threshold)
                if result["passes"]:
                    candidates.append(result)

    # Pre-registered selection: prefer broader support; then higher all40 mean;
    # then smaller absolute threshold only as a deterministic tie-break.
    candidates.sort(
        key=lambda x: (
            -x["support"],
            -x["conditional_all40_self"]["mean"],
            abs(x["threshold"]),
            x["feature"],
            x["operator"],
        )
    )
    selected = candidates[0] if candidates else None

    result = {
        "schema": "kaggriculture.closure-receiver-final-separator-audit.v0",
        "source_population": "fresh40-4902-4941",
        "source_run": 35566515651,
        "candidate": {
            "abstraction": "option_preserving",
            "gain": GAIN,
        },
        "allowed_features": list(FEATURES),
        "criteria": {
            "single_feature_single_threshold_only": True,
            "min_support": MIN_SUPPORT,
            "enabled_mean_self_gt_zero": True,
            "enabled_improved_gt_worsened": True,
            "enabled_large_loss_threshold": LARGE_LOSS,
            "enabled_large_loss_count_must_equal": 0,
            "conditional_all40_mean_self_gt_zero": True,
            "independent_unseen_validation_required": True,
        },
        "fresh40_reproduction": observed_summary,
        "rows": rows,
        "passing_separator_count": len(candidates),
        "selected_separator": selected,
        "decision": (
            "ONE_SEPARATOR_FOR_INDEPENDENT_BATTLE"
            if selected is not None
            else "NO_DEPLOYABLE_SEPARATOR_CLOSE_CLOSURE_RECEIVER"
        ),
        "boundary": {
            "discovery_only": True,
            "new_observer_fields": False,
            "receiver_features_forbidden": True,
            "seat_forbidden": True,
            "terminal_features_forbidden": True,
            "complex_feature_combinations_forbidden": True,
            "max_returned_separator": 1,
            "promote": False,
            "adopt": False,
        },
    }

    Path("closure_receiver_final_separator_audit_v0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("FINAL_SEPARATOR_AUDIT " + json.dumps({
        "fresh40_reproduction": observed_summary,
        "passing_separator_count": len(candidates),
        "selected_separator": selected,
        "decision": result["decision"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
