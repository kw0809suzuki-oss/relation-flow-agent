#!/usr/bin/env python3
"""Stratified robustness battle for frozen Payback Closure Candidate v0.

Frozen candidate:
    remaining horizon <= 14 -> suppress new expansion purchases

Three opponent conditions x same five paired seeds.
Read per-condition signs; do not collapse to one grand mean.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make
import g17_agent as current
import payback_closure_candidate_v0 as candidate

CASES = [(5601+i, i%2) for i in range(5)]
OPPONENTS = {
    "Seyamalam": "opponents/seyamalam_v21.py",
    "lonespear": "opponents/lonespear_main.py",
    "COK": "opponents/cok_main.py",
}
OUT = Path("payback_closure_stratified_robustness_v0.json")


def configure(module):
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
    module.set_probe_enabled(True)
    module.set_attribution_enabled(True)
    if hasattr(module, "reset_experiment"):
        module.reset_experiment()
    else:
        module.reset_telemetry()


def play(fn, module, opponent, seed, seat):
    configure(module)
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [opponent, opponent]
    players[seat] = fn
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    acts = module.get_activations() if hasattr(module, "get_activations") else []
    return {
        "self": rewards[seat],
        "opp": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
        "win": rewards[seat] > rewards[1-seat],
        "activations": acts,
    }


def mean(xs):
    return sum(xs)/len(xs) if xs else None


def summarize(rows):
    return {
        "case_count": len(rows),
        "activated_cases": sum(r["activation_count"] > 0 for r in rows),
        "activation_count": sum(r["activation_count"] for r in rows),
        "improved": sum(r["self_diff"] > 0 for r in rows),
        "worsened": sum(r["self_diff"] < 0 for r in rows),
        "equal": sum(r["self_diff"] == 0 for r in rows),
        "mean_self_diff": mean([r["self_diff"] for r in rows]),
        "mean_margin_diff": mean([r["margin_diff"] for r in rows]),
        "current_wins": sum(r["current"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate"]["win"] for r in rows),
    }


def main():
    all_rows = []
    by_condition = {}

    for label, opponent in OPPONENTS.items():
        rows = []
        for seed, seat in CASES:
            b = play(current.agent, current, opponent, seed, seat)
            c = play(candidate.agent, candidate, opponent, seed, seat)
            row = {
                "condition": label,
                "seed": seed,
                "seat": seat,
                "activation_count": len(c["activations"]),
                "activation_days": sorted({a["day"] for a in c["activations"]}),
                "current": {"self": b["self"], "margin": b["margin"], "win": b["win"]},
                "candidate": {"self": c["self"], "margin": c["margin"], "win": c["win"]},
                "self_diff": c["self"] - b["self"],
                "margin_diff": c["margin"] - b["margin"],
            }
            rows.append(row)
            all_rows.append(row)
        by_condition[label] = summarize(rows)

    result = {
        "schema": "kaggriculture.payback-closure.stratified-robustness.v0",
        "frozen_candidate": "remaining_horizon <= 14 => suppress new expansion purchases",
        "opponents": {
            "Seyamalam": {"sha": "8b8c421eb10634c756583ce10c75189f50c83a72"},
            "lonespear": {"sha": "774b26093ccf4246525517d48420349b841b6e50"},
            "COK": {"sha": "7ef67eac458cd9ecd13786063e2e581fbe7403ec"},
        },
        "cases_per_condition": CASES,
        "boundary": [
            "Gate logic and threshold are frozen from prior fresh10 replications.",
            "Primary read is per-condition sign, not a grand mean.",
            "No post-hoc rule repair from individual losing seeds."
        ],
        "summary_by_condition": by_condition,
        "rows": all_rows,
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PAYBACK_CLOSURE_STRATIFIED_SUMMARY " + json.dumps(by_condition, separators=(",", ":")))
    print("PAYBACK_CLOSURE_STRATIFIED_ROWS " + json.dumps(all_rows, separators=(",", ":")))


if __name__ == "__main__":
    main()
