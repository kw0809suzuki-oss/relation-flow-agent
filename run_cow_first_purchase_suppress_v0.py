#!/usr/bin/env python3
import json
import os

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT
KNOWN = [(3206, 0)]
FRESH10 = [(4402 + i, i % 2) for i in range(10)]


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()


def play(agent_fn, seed, seat, reset=None):
    configure()
    if reset:
        reset()
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


def run(cases):
    rows = []
    for seed, seat in cases:
        b = play(baseline.agent, seed, seat)
        c = play(candidate.agent, seed, seat, candidate.reset_experiment)
        acts = candidate.get_activations()
        rows.append({
            "seed": seed,
            "seat": seat,
            "activation_count": len(acts),
            "activations": acts,
            "baseline": b,
            "candidate": c,
            "self_diff": c["self"] - b["self"],
            "opp_diff": c["opp"] - b["opp"],
            "margin_diff": c["margin"] - b["margin"],
        })

    n = len(rows)
    return {
        "cases": rows,
        "summary": {
            "case_count": n,
            "activated_cases": sum(r["activation_count"] > 0 for r in rows),
            "activation_count": sum(r["activation_count"] for r in rows),
            "improved": sum(r["self_diff"] > 0 for r in rows),
            "worsened": sum(r["self_diff"] < 0 for r in rows),
            "equal": sum(r["self_diff"] == 0 for r in rows),
            "mean_self_diff": sum(r["self_diff"] for r in rows) / n,
            "mean_margin_diff": sum(r["margin_diff"] for r in rows) / n,
        },
    }


def main():
    known = run(KNOWN)
    fresh10 = run(FRESH10)
    out = {
        "schema": "cow-first-purchase-suppress.v0",
        "objective": "terminal self money; margin supplemental",
        "intervention": "suppress first native BUY_ANIMAL COW 1 once per match",
        "interpretation_boundary": "persistent-state intervention probe only; not an adopted Combat Rule",
        "known3206": known,
        "fresh10": fresh10,
    }
    with open("cow_first_purchase_suppress_v0.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("COW_FIRST_PURCHASE_SUPPRESS_KNOWN " + json.dumps(known["summary"], separators=(",", ":")))
    print("COW_FIRST_PURCHASE_SUPPRESS_FRESH10 " + json.dumps(fresh10["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
