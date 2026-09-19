#!/usr/bin/env python3
"""A/B/C main-line connection test.

A: Current G17
B: Frozen 14-day Closure only
C: Frozen 14-day Closure + coarse Cash/Recovery Switch

Same five seeds under each of three already-used opponent conditions.
Primary question: does C move terminal outcomes beyond B?
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
import payback_closure_candidate_v0 as closure
import closure_cash_switch_candidate_v0 as switch

CASES = [(5901+i, i % 2) for i in range(5)]
OPPONENTS = {
    "Seyamalam": "opponents/seyamalam_v21.py",
    "lonespear": "opponents/lonespear_main.py",
    "COK": "opponents/cok_main.py",
}
OUT = Path("closure_switch_mainline_abc_v0.json")


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
    activations = module.get_activations() if hasattr(module, "get_activations") else []
    switch_events = module.get_switch_events() if hasattr(module, "get_switch_events") else []
    return {
        "self": rewards[seat],
        "opp": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
        "win": rewards[seat] > rewards[1-seat],
        "activation_count": len(activations),
        "switch_event_count": len(switch_events),
        "switch_event_days": sorted({e["day"] for e in switch_events}),
    }


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def summarize(rows):
    return {
        "cases": len(rows),
        "b_better_than_a": sum(r["B_minus_A_self"] > 0 for r in rows),
        "b_worse_than_a": sum(r["B_minus_A_self"] < 0 for r in rows),
        "c_better_than_b": sum(r["C_minus_B_self"] > 0 for r in rows),
        "c_worse_than_b": sum(r["C_minus_B_self"] < 0 for r in rows),
        "c_equal_b": sum(r["C_minus_B_self"] == 0 for r in rows),
        "mean_B_minus_A_self": mean([r["B_minus_A_self"] for r in rows]),
        "mean_C_minus_B_self": mean([r["C_minus_B_self"] for r in rows]),
        "mean_C_minus_B_margin": mean([r["C_minus_B_margin"] for r in rows]),
        "A_wins": sum(r["A"]["win"] for r in rows),
        "B_wins": sum(r["B"]["win"] for r in rows),
        "C_wins": sum(r["C"]["win"] for r in rows),
        "B_activated": sum(r["B"]["activation_count"] > 0 for r in rows),
        "C_activated": sum(r["C"]["activation_count"] > 0 for r in rows),
        "C_switch_fired": sum(r["C"]["switch_event_count"] > 0 for r in rows),
    }


def main():
    by_condition = {}
    all_rows = []

    for condition, opponent in OPPONENTS.items():
        rows = []
        for seed, seat in CASES:
            a = play(current.agent, current, opponent, seed, seat)
            b = play(closure.agent, closure, opponent, seed, seat)
            c = play(switch.agent, switch, opponent, seed, seat)

            row = {
                "condition": condition,
                "seed": seed,
                "seat": seat,
                "A": a,
                "B": b,
                "C": c,
                "B_minus_A_self": b["self"] - a["self"],
                "C_minus_B_self": c["self"] - b["self"],
                "C_minus_B_margin": c["margin"] - b["margin"],
            }
            rows.append(row)
            all_rows.append(row)
        by_condition[condition] = summarize(rows)

    result = {
        "schema": "kaggriculture.closure-switch-mainline.abc.v0",
        "A": "Current G17",
        "B": "Frozen Closure only: remaining_horizon <= 14 suppress new expansion purchases",
        "C": "B + coarse Switch: suppress HIRE and harvest immediately when standing on harvestable output",
        "boundary": [
            "14-day Closure gate is unchanged.",
            "Switch is intentionally coarse; this is not an optimization search.",
            "Primary read is C versus B, per battle condition.",
            "If C is worse, do not rescue the Switch with extra conditions."
        ],
        "cases_per_condition": CASES,
        "summary_by_condition": by_condition,
        "rows": all_rows,
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CLOSURE_SWITCH_ABC_SUMMARY " + json.dumps(by_condition, separators=(",", ":")))
    print("CLOSURE_SWITCH_ABC_ROWS " + json.dumps(all_rows, separators=(",", ":")))


if __name__ == "__main__":
    main()
