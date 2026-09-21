#!/usr/bin/env python3
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as native
import cow_first_purchase_suppress_v0 as cow
import cow_day8_low_price_milk_rescue_v0 as rescue

OPPONENT = base.OPPONENT

KNOWN10 = [(4402 + i, i % 2) for i in range(10)]
FRESH20 = [(4702 + i, i % 2) for i in range(20)]


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    native.set_control_enabled(False)
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()


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
        "opp": rewards[1 - seat],
        "margin": rewards[seat] - rewards[1 - seat],
    }


def compare(a, b):
    return {
        "self_diff": b["self"] - a["self"],
        "opp_diff": b["opp"] - a["opp"],
        "margin_diff": b["margin"] - a["margin"],
    }


def summarize(rows, key):
    vals = [r[key] for r in rows]
    n = len(vals)
    mean = lambda field: sum(v[field] for v in vals) / n if n else 0.0
    return {
        "case_count": n,
        "mean_self_diff": mean("self_diff"),
        "mean_opp_diff": mean("opp_diff"),
        "mean_margin_diff": mean("margin_diff"),
        "improved_self": sum(v["self_diff"] > 0 for v in vals),
        "worsened_self": sum(v["self_diff"] < 0 for v in vals),
        "equal_self": sum(v["self_diff"] == 0 for v in vals),
        "improved_margin": sum(v["margin_diff"] > 0 for v in vals),
        "worsened_margin": sum(v["margin_diff"] < 0 for v in vals),
        "equal_margin": sum(v["margin_diff"] == 0 for v in vals),
    }


def run_bundle(name, cases):
    rows = []
    for seed, seat in cases:
        n = play(native.agent, seed, seat)
        c = play(cow.agent, seed, seat, cow.reset_experiment)
        cow_activations = cow.get_activations()

        r = play(rescue.agent, seed, seat, rescue.reset_experiment)
        hold_events = rescue.get_hold_events()
        rescue_cow_activations = rescue.get_cow_activations()

        row = {
            "seed": seed,
            "seat": seat,
            "native": n,
            "cow": c,
            "rescue": r,
            "cow_vs_native": compare(n, c),
            "rescue_vs_cow": compare(c, r),
            "rescue_vs_native": compare(n, r),
            "cow_activation_count": len(cow_activations),
            "rescue_cow_activation_count": len(rescue_cow_activations),
            "hold_activation_count": len(hold_events),
            "hold_events": hold_events,
        }
        rows.append(row)
        print(
            "CASE "
            + json.dumps(
                {
                    "bundle": name,
                    "seed": seed,
                    "seat": seat,
                    "hold": len(hold_events),
                    "cow_self_diff": row["cow_vs_native"]["self_diff"],
                    "rescue_vs_cow_self_diff": row["rescue_vs_cow"]["self_diff"],
                    "rescue_vs_native_self_diff": row["rescue_vs_native"]["self_diff"],
                    "rescue_vs_cow_margin_diff": row["rescue_vs_cow"]["margin_diff"],
                },
                separators=(",", ":"),
            )
        )

    return {
        "name": name,
        "cases": rows,
        "summary": {
            "cow_vs_native": summarize(rows, "cow_vs_native"),
            "rescue_vs_cow": summarize(rows, "rescue_vs_cow"),
            "rescue_vs_native": summarize(rows, "rescue_vs_native"),
            "hold_activated_cases": sum(r["hold_activation_count"] > 0 for r in rows),
            "hold_activation_count": sum(r["hold_activation_count"] for r in rows),
        },
    }


def subset_summary(rows, seeds):
    chosen = [r for r in rows if r["seed"] in seeds]
    return {
        "seeds": sorted(seeds),
        "rescue_vs_cow": summarize(chosen, "rescue_vs_cow"),
        "rescue_vs_native": summarize(chosen, "rescue_vs_native"),
        "hold_activated_cases": sum(r["hold_activation_count"] > 0 for r in chosen),
    }


def main():
    known = run_bundle("known10_4402_4411", KNOWN10)
    fresh = run_bundle("fresh20_4702_4721", FRESH20)

    out = {
        "schema": "kaggriculture.cow-day8-low-price-milk-rescue.v0",
        "candidate": {
            "base": "COW First Purchase Suppress v0",
            "change": "remove SELL MILK once on Day8 when current MILK price < 180",
            "threshold": 180.0,
            "target_day": 8,
            "one_shot": True,
            "next_turn_returns_to_cow_policy": True,
            "threshold_note": "same threshold as rejected MILK Hold v1; intervention timing moved from Day9-10 to Day8",
        },
        "evidence_origin": {
            "known_accident3": [4404, 4407, 4409],
            "known_nonaccident_negative": [4406],
            "observed_separator": "candidate MILK price at turn197/day8/hour5: accident3=175, improved6>=196",
            "causal_claim_before_battle": False,
        },
        "bundles": {
            "known10": known,
            "fresh20": fresh,
        },
        "known_subsets": {
            "accident3": subset_summary(known["cases"], {4404, 4407, 4409}),
            "improved6": subset_summary(known["cases"], {4402, 4403, 4405, 4408, 4410, 4411}),
            "seed4406": subset_summary(known["cases"], {4406}),
        },
        "boundary": {
            "battle_candidate_only": True,
            "observer_expansion": False,
            "promote": False,
            "adopt": False,
        },
    }

    Path("cow_day8_low_price_milk_rescue_v0.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("KNOWN10 " + json.dumps(known["summary"], separators=(",", ":")))
    print("FRESH20 " + json.dumps(fresh["summary"], separators=(",", ":")))
    print("ACCIDENT3 " + json.dumps(out["known_subsets"]["accident3"], separators=(",", ":")))


if __name__ == "__main__":
    main()
