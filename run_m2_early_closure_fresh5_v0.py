#!/usr/bin/env python3
"""Paired fresh5 smoke for M2 Early Closure v0 vs frozen G17 Current."""

import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as current
import m2_early_closure_v0 as m2

OPPONENT = base.OPPONENT
CASES = [(5201 + i, i % 2) for i in range(5)]
OUTPUT = Path("m2_early_closure_fresh5_v0.json")


def configure(agent_module):
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
    agent_module.set_probe_enabled(True)
    agent_module.set_attribution_enabled(True)
    if hasattr(agent_module, "reset_experiment"):
        agent_module.reset_experiment()
    else:
        agent_module.reset_telemetry()


def play(agent_fn, module, seed, seat):
    configure(module)
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = agent_fn
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return {
        "self": rewards[seat],
        "opp": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
    }


def main():
    rows = []
    for seed, seat in CASES:
        b = play(current.agent, current, seed, seat)
        c = play(m2.agent, m2, seed, seat)
        acts = m2.get_activations()
        rows.append({
            "seed": seed,
            "seat": seat,
            "activation_count": len(acts),
            "activation_days": sorted({a["day"] for a in acts}),
            "baseline": b,
            "candidate": c,
            "self_diff": c["self"] - b["self"],
            "margin_diff": c["margin"] - b["margin"],
        })

    activated = [r for r in rows if r["activation_count"] > 0]
    summary = {
        "case_count": len(rows),
        "activated_cases": len(activated),
        "activation_count": sum(r["activation_count"] for r in rows),
        "improved": sum(r["self_diff"] > 0 for r in activated),
        "worsened": sum(r["self_diff"] < 0 for r in activated),
        "equal": sum(r["self_diff"] == 0 for r in activated),
        "mean_self_diff_activated": (
            sum(r["self_diff"] for r in activated) / len(activated)
            if activated else None
        ),
        "mean_margin_diff_activated": (
            sum(r["margin_diff"] for r in activated) / len(activated)
            if activated else None
        ),
    }

    payload = {
        "schema": "kaggriculture.m2-early-closure.v0",
        "variant": "M2 Early Closure",
        "bias": "day>=20: suppress new BUY_LAND/BUY_SEED/BUY_ANIMAL/COW purchases only",
        "boundary": "Day20 is a test knob, not an inferred optimum. No adoption from fresh5.",
        "rows": rows,
        "summary": summary,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("M2_EARLY_CLOSURE_SUMMARY " + json.dumps(summary, separators=(",", ":")))
    print("M2_EARLY_CLOSURE_ROWS " + json.dumps(rows, separators=(",", ":")))


if __name__ == "__main__":
    main()
