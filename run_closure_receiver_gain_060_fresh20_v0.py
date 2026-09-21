#!/usr/bin/env python3
"""Fresh paired Battle for Closure receiver gain 0.60.

Candidate only:
- abstraction = option_preserving
- gain = 0.60
- native Origin keeps direction
- compare against no-abstraction baseline
- no promotion/adoption in this run
"""

import copy
import json
import os
from pathlib import Path
from statistics import mean, median

from kaggle_environments import make
import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((4802 + i, i % 2) for i in range(20))
GAIN = 0.60


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
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    return min(len(left), len(right)) if len(left) != len(right) else None


def diff_count(left, right):
    return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat)
        candidate = play(seed, seat, "option_preserving", GAIN)
        delta = {
            k: candidate["score"][k] - baseline["score"][k]
            for k in ("self", "opponent", "margin")
        }
        row = {
            "seed": seed,
            "seat": seat,
            "baseline_score": baseline["score"],
            "candidate_score": candidate["score"],
            "terminal_delta": delta,
            "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
            "action_difference_count": diff_count(candidate["actions"], baseline["actions"]),
            "candidate_response": {
                "received_snapshots": candidate["received_snapshots"],
                "effect_snapshots": candidate["effect_snapshots"],
                "gain_seen": candidate["gain_seen"],
                "snapshot_count": candidate["snapshot_count"],
            },
            "causal_attribution": False,
            "promote": False,
        }
        rows.append(row)
        print("CASE " + json.dumps({
            "seed": seed,
            "seat": seat,
            "self_diff": delta["self"],
            "margin_diff": delta["margin"],
            "action_differences": row["action_difference_count"],
        }, separators=(",", ":")))

    self_deltas = [r["terminal_delta"]["self"] for r in rows]
    margin_deltas = [r["terminal_delta"]["margin"] for r in rows]
    action_diffs = [r["action_difference_count"] for r in rows]

    summary = {
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
            "action_difference_cases": sum(x > 0 for x in action_diffs),
            "total_action_differences": sum(action_diffs),
            "median_action_differences": median(action_diffs),
        },
    }

    result = {
        "schema": "kaggriculture.closure-receiver-gain-060.fresh20.v0",
        "question": "Does option_preserving gain 0.60 reproduce terminal-self improvement on fresh paired Battles?",
        "benchmark": {
            "name": "fresh20-4802-4821",
            "cases": [{"seed": s, "seat": seat} for s, seat in CASES],
            "disjoint_from_gain_sweep_known12": True,
        },
        "candidate": {
            "abstraction": "option_preserving",
            "gain": GAIN,
            "direction_source": "native_origin",
            "direct_action_instruction": False,
            "receiver": "origin crop commitment scaling",
        },
        "rows": rows,
        "summary": summary,
        "boundary": {
            "candidate_only": True,
            "causal_attribution": False,
            "promote": False,
            "adopt": False,
        },
    }

    Path("closure_receiver_gain_060_fresh20_v0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CLOSURE_RECEIVER_GAIN_060_FRESH20 " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
