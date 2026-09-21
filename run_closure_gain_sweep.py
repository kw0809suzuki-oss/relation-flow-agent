#!/usr/bin/env python3
"""Closure Abstract Transmission gain sweep on a fixed 12-case benchmark.

This is an experiment-only probe. It does not promote or adopt any rule.
"""

import copy
import json
import os
from pathlib import Path
from statistics import mean, median

from kaggle_environments import make
import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
CASES = (
    (3202, 0), (3206, 0), (3215, 1), (3218, 0),
    (3222, 0), (3227, 1), (3231, 1), (3240, 0),
    (3243, 1), (3246, 0), (3250, 0), (3251, 1),
)
GAINS = (0.75, 0.60, 0.45)


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


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def snapshots(trace):
    try:
        return trace["body"]["observe"]["body"]["snapshots"]
    except Exception:
        return []


def play(seed, seat, abstraction=None, gain=None):
    configure(abstraction, gain)
    actions = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        action = agent.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    trace = agent.get_trace()
    snaps = snapshots(trace)

    received = sum(
        1 for s in snaps
        if (s.get("origin_integration") or {}).get("strategy_instruction") == abstraction
    ) if abstraction else 0
    affected = sum(
        1 for s in snaps
        if (s.get("origin_integration") or {}).get("abstraction_effect")
        == "reduce_commitment_preserve_optional_space"
    )
    gain_seen = sorted({
        (s.get("origin_integration") or {}).get("abstraction_gain")
        for s in snaps
        if (s.get("origin_integration") or {}).get("abstraction_gain") is not None
    })

    return {
        "score": score(rewards, seat),
        "actions": actions,
        "received_snapshots": received,
        "effect_snapshots": affected,
        "gain_seen": gain_seen,
        "snapshot_count": len(snaps),
    }


def first_difference(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def diff_count(left, right):
    common = sum(a != b for a, b in zip(left, right))
    return common + abs(len(left) - len(right))


def summarize_arm(rows):
    self_deltas = [r["terminal_delta"]["self"] for r in rows]
    margin_deltas = [r["terminal_delta"]["margin"] for r in rows]
    action_counts = [r["action_difference_count"] for r in rows]
    return {
        "battle_count": len(rows),
        "self": {
            "improved": sum(x > 0 for x in self_deltas),
            "worsened": sum(x < 0 for x in self_deltas),
            "equal": sum(x == 0 for x in self_deltas),
            "mean_delta": mean(self_deltas),
            "median_delta": median(self_deltas),
            "min_delta": min(self_deltas),
            "max_delta": max(self_deltas),
        },
        "margin": {
            "improved": sum(x > 0 for x in margin_deltas),
            "worsened": sum(x < 0 for x in margin_deltas),
            "equal": sum(x == 0 for x in margin_deltas),
            "mean_delta": mean(margin_deltas),
            "median_delta": median(margin_deltas),
            "min_delta": min(margin_deltas),
            "max_delta": max(margin_deltas),
        },
        "receiver": {
            "received_snapshots": sum(r["candidate_response"]["received_snapshots"] for r in rows),
            "effect_snapshots": sum(r["candidate_response"]["effect_snapshots"] for r in rows),
            "action_difference_cases": sum(x > 0 for x in action_counts),
            "total_action_differences": sum(action_counts),
            "median_action_differences": median(action_counts),
        },
    }


def main():
    baselines = {}
    for seed, seat in CASES:
        baselines[(seed, seat)] = play(seed, seat)

    arms = {}
    for gain in GAINS:
        rows = []
        for seed, seat in CASES:
            baseline = baselines[(seed, seat)]
            candidate = play(seed, seat, "option_preserving", gain)
            delta = {
                k: candidate["score"][k] - baseline["score"][k]
                for k in ("self", "opponent", "margin")
            }
            action_difference_count = diff_count(candidate["actions"], baseline["actions"])
            rows.append({
                "seed": seed,
                "seat": seat,
                "gain": gain,
                "baseline_score": baseline["score"],
                "candidate_score": candidate["score"],
                "terminal_delta": delta,
                "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
                "action_difference_count": action_difference_count,
                "candidate_response": {
                    "received_snapshots": candidate["received_snapshots"],
                    "effect_snapshots": candidate["effect_snapshots"],
                    "gain_seen": candidate["gain_seen"],
                    "snapshot_count": candidate["snapshot_count"],
                },
                "causal_attribution": False,
                "promote": False,
            })
        key = f"{gain:.2f}"
        arms[key] = {"rows": rows, "summary": summarize_arm(rows)}

    result = {
        "schema": "kaggriculture.closure-abstract-transmission.gain-sweep.v0",
        "question": "Does stronger option-preserving transmission gain change receiver coverage and terminal outcomes coherently?",
        "benchmark": {
            "name": "known-fixed-12",
            "cases": [{"seed": s, "seat": seat} for s, seat in CASES],
            "note": "This is a new fixed benchmark, not a reproduction of the prior C12/C14 paired-20 set.",
        },
        "abstraction": {
            "name": "option_preserving",
            "direct_action_instruction": False,
            "direction_source": "native_origin",
            "receiver": "origin crop commitment scaling",
            "gains": list(GAINS),
        },
        "arms": arms,
        "boundary": "experimental_gain_sweep_no_rule_promotion",
        "causal_attribution": False,
        "promote": False,
    }

    Path("closure_gain_sweep_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    compact = {gain: data["summary"] for gain, data in arms.items()}
    print("CLOSURE_GAIN_SWEEP " + json.dumps(compact, separators=(",", ":")))


if __name__ == "__main__":
    main()
