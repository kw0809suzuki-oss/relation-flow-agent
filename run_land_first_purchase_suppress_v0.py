#!/usr/bin/env python3
import json
import os

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import land_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT

KNOWN13 = [
    (4129,1),(4130,0),(4131,1),
    (4142,0),(4143,1),(4144,0),
    (4147,1),(4149,1),(4151,1),
    (4152,0),(4156,0),(4158,0),(4161,1)
]

FRESH10 = [(4502+i, i%2) for i in range(10)]


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
            "activation_day": acts[0].get("day") if acts else None,
            "baseline": b,
            "candidate": c,
            "self_diff": c["self"] - b["self"],
            "margin_diff": c["margin"] - b["margin"],
        })

    activated = [r for r in rows if r["activation_count"] > 0]
    return {
        "cases": rows,
        "summary": {
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
    }


def main():
    known = run(KNOWN13)
    fresh = run(FRESH10)
    out = {
        "schema": "land-first-purchase-suppress.v0",
        "objective": "fill LAND Terminal gate; terminal self primary",
        "intervention": "suppress first native BUY_LAND once per match",
        "boundary": "Terminal gate probe only; Direction is not interpreted yet.",
        "known13": known,
        "fresh10": fresh,
    }
    with open("land_first_purchase_suppress_v0.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
        f.write("\n")

    print("LAND_FIRST_PURCHASE_SUPPRESS_KNOWN13 "+json.dumps(known["summary"],separators=(",",":")))
    print("LAND_FIRST_PURCHASE_SUPPRESS_FRESH10 "+json.dumps(fresh["summary"],separators=(",",":")))
    print("LAND_FIRST_PURCHASE_SUPPRESS_ROWS "+json.dumps([
        {
            "seed":r["seed"],
            "seat":r["seat"],
            "activation_count":r["activation_count"],
            "activation_day":r["activation_day"],
            "self_diff":r["self_diff"],
        }
        for r in fresh["cases"]
    ],separators=(",",":")))


if __name__ == "__main__":
    main()
