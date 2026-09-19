#!/usr/bin/env python3
"""Mixed-win opponent band calibration + independent frozen-gate Battle.

The 14-day closure gate is frozen. Opponent selection is done only to obtain
a battle band where Current G17 produces both wins and losses.

Pilot:
- Current G17 vs three existing independent opponent agents
- 6 paired seat-balanced seeds
- eligible opponent must produce both Current wins and losses
- select eligible opponent closest to 50% Current win rate

Validation:
- independent fresh10
- Current G17 vs selected opponent
- frozen Payback Closure Candidate v0 vs same opponent
- compare terminal self, margin, wins, activation, improved/worsened
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import agent as base_agent
import g7_agent
import strong_origin
import g17_agent as current
import payback_closure_candidate_v0 as candidate

PILOT_CASES = [(5701+i, i % 2) for i in range(6)]
VALIDATION_CASES = [(5801+i, i % 2) for i in range(10)]
OUT = Path("payback_closure_mixed_win_band_v0.json")

OPPONENTS = {
    "Strong Origin": (strong_origin.agent, strong_origin),
    "G7": (g7_agent.agent, g7_agent),
    "Base Agent": (base_agent.agent, base_agent),
}


def configure_subject(module):
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


def reset_opponent(module):
    if hasattr(module, "reset_telemetry"):
        module.reset_telemetry()


def play(subject_fn, subject_module, opponent_fn, opponent_module, seed, seat):
    configure_subject(subject_module)
    reset_opponent(opponent_module)
    players = [opponent_fn, opponent_fn]
    players[seat] = subject_fn
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    activations = (
        subject_module.get_activations()
        if hasattr(subject_module, "get_activations")
        else []
    )
    return {
        "self": rewards[seat],
        "opp": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
        "win": rewards[seat] > rewards[1-seat],
        "activations": activations,
    }


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def pilot():
    results = {}
    for label, (opp_fn, opp_module) in OPPONENTS.items():
        rows = []
        for seed, seat in PILOT_CASES:
            r = play(current.agent, current, opp_fn, opp_module, seed, seat)
            rows.append({
                "seed": seed,
                "seat": seat,
                "self": r["self"],
                "margin": r["margin"],
                "win": r["win"],
            })
        wins = sum(r["win"] for r in rows)
        losses = len(rows) - wins
        results[label] = {
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(rows),
            "mixed": wins > 0 and losses > 0,
            "rows": rows,
        }
    eligible = [
        (abs(v["win_rate"] - 0.5), label)
        for label, v in results.items()
        if v["mixed"]
    ]
    selected = min(eligible)[1] if eligible else None
    return results, selected


def validate(selected):
    opp_fn, opp_module = OPPONENTS[selected]
    rows = []
    for seed, seat in VALIDATION_CASES:
        b = play(current.agent, current, opp_fn, opp_module, seed, seat)
        c = play(candidate.agent, candidate, opp_fn, opp_module, seed, seat)
        rows.append({
            "seed": seed,
            "seat": seat,
            "activation_count": len(c["activations"]),
            "activation_days": sorted({a["day"] for a in c["activations"]}),
            "current": {
                "self": b["self"],
                "margin": b["margin"],
                "win": b["win"],
            },
            "candidate": {
                "self": c["self"],
                "margin": c["margin"],
                "win": c["win"],
            },
            "self_diff": c["self"] - b["self"],
            "margin_diff": c["margin"] - b["margin"],
            "win_delta": int(c["win"]) - int(b["win"]),
        })
    summary = {
        "case_count": len(rows),
        "activated_cases": sum(r["activation_count"] > 0 for r in rows),
        "activation_count": sum(r["activation_count"] for r in rows),
        "improved": sum(r["self_diff"] > 0 for r in rows),
        "worsened": sum(r["self_diff"] < 0 for r in rows),
        "equal": sum(r["self_diff"] == 0 for r in rows),
        "mean_self_current": mean([r["current"]["self"] for r in rows]),
        "mean_self_candidate": mean([r["candidate"]["self"] for r in rows]),
        "mean_self_diff": mean([r["self_diff"] for r in rows]),
        "mean_margin_diff": mean([r["margin_diff"] for r in rows]),
        "current_wins": sum(r["current"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate"]["win"] for r in rows),
        "wins_gained": sum(r["win_delta"] > 0 for r in rows),
        "wins_lost": sum(r["win_delta"] < 0 for r in rows),
    }
    return rows, summary


def main():
    pilot_results, selected = pilot()
    result = {
        "schema": "kaggriculture.payback-closure.mixed-win-band.v0",
        "frozen_candidate": "remaining_horizon <= 14 => suppress new expansion purchases",
        "pilot_cases": PILOT_CASES,
        "pilot": pilot_results,
        "selected_opponent": selected,
        "validation_cases": VALIDATION_CASES,
        "boundary": [
            "The 14-day gate and threshold are unchanged.",
            "Pilot seeds select only an opponent band; validation uses independent seeds.",
            "No opponent qualifies if Current does not show both wins and losses.",
        ],
    }

    print("MIXED_WIN_BAND_PILOT " + json.dumps({
        k: {x:v[x] for x in ("wins","losses","win_rate","mixed")}
        for k,v in pilot_results.items()
    }, separators=(",", ":")))
    print("MIXED_WIN_BAND_SELECTED " + json.dumps({"selected": selected}, separators=(",", ":")))

    if selected is not None:
        rows, summary = validate(selected)
        result["validation_summary"] = summary
        result["validation_rows"] = rows
        print("MIXED_WIN_BAND_VALIDATION_SUMMARY " + json.dumps(summary, separators=(",", ":")))
        print("MIXED_WIN_BAND_VALIDATION_ROWS " + json.dumps(rows, separators=(",", ":")))

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
