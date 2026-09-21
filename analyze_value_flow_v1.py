#!/usr/bin/env python3
"""Locate the first coarse value-flow bottleneck without mutating the Agent.

Coordinate is deliberately fixed:
capital -> expansion -> operation -> production -> recovery -> terminal.
This is an observer, not a new controller. It consumes the existing reproducible
Scale baseline artifact and reports only coarse stage evidence that can change
the next implementation decision.
"""

import json
from pathlib import Path
from statistics import mean

INPUT = Path("scale_baseline_v1.json")
OUTPUT = Path("value_flow_v1.json")


def _case_summary(case):
    obs = case["observations"]
    if not obs:
        return None
    start, end = obs[0], obs[-1]
    peak_land = max(r["land"] for r in obs)
    peak_hands = max(r["hands"] for r in obs)
    expansion_days = sum(
        1 for a, b in zip(obs, obs[1:])
        if b["land"] > a["land"] or b["hands"] > a["hands"]
    )
    active_days = sum(1 for r in obs if r["hands"] > 0)
    recovery_days = sum(1 for r in obs if r["collected_value"] > 0)
    recovered_value = sum(r["collected_value"] for r in obs)
    produced_known = [r["produced_value"] for r in obs if r["produced_value"] is not None]
    return {
        "seed": case["seed"],
        "seat": case["seat"],
        "terminal_self": case["terminal"]["self"],
        "terminal_margin": case["terminal"]["margin"],
        "capital_start": start["money"],
        "capital_end": end["money"],
        "peak_land": peak_land,
        "peak_hands": peak_hands,
        "expansion_days": expansion_days,
        "active_day_ratio": active_days / len(obs),
        "production_observable": bool(produced_known),
        "peak_inventory_value": max(produced_known) if produced_known else None,
        "recovery_days": recovery_days,
        "recovered_value": recovered_value,
    }


def main():
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    cases = [x for c in payload["cases"] if (x := _case_summary(c)) is not None]
    production_known = sum(c["production_observable"] for c in cases)

    aggregate = {
        "case_count": len(cases),
        "mean_terminal_self": mean(c["terminal_self"] for c in cases),
        "mean_terminal_margin": mean(c["terminal_margin"] for c in cases),
        "mean_peak_land": mean(c["peak_land"] for c in cases),
        "mean_peak_hands": mean(c["peak_hands"] for c in cases),
        "mean_expansion_days": mean(c["expansion_days"] for c in cases),
        "mean_active_day_ratio": mean(c["active_day_ratio"] for c in cases),
        "production_observable_cases": production_known,
        "mean_recovery_days": mean(c["recovery_days"] for c in cases),
        "mean_recovered_value": mean(c["recovered_value"] for c in cases),
    }

    # Evidence boundary: do not manufacture a production diagnosis when the
    # exporter cannot observe production. The first coarse stage that can be
    # named must be supported by current measurements.
    if aggregate["mean_expansion_days"] == 0:
        first_observed_bottleneck = "expansion"
    elif aggregate["mean_active_day_ratio"] < 0.5:
        first_observed_bottleneck = "operation"
    elif production_known == 0:
        first_observed_bottleneck = "unresolved_between_production_and_recovery"
    elif aggregate["mean_recovery_days"] == 0:
        first_observed_bottleneck = "recovery"
    else:
        first_observed_bottleneck = "not_identified_from_current_coarse_observation"

    out = {
        "schema": "kaggriculture.value-flow-observer.v1",
        "coordinate": ["capital", "expansion", "operation", "production", "recovery", "terminal"],
        "baseline_identity": payload.get("baseline_identity"),
        "policy_mutated": False,
        "aggregate": aggregate,
        "first_observed_bottleneck": first_observed_bottleneck,
        "cases": cases,
        "boundary": [
            "descriptive coarse observation only; no causal attribution",
            "collected_value remains positive daily money delta",
            "if production is unobservable, stop there rather than inventing a bottleneck",
            "next implementation must change one existing component only and be judged by paired terminal A/B",
        ],
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("VALUE_FLOW_V1 " + json.dumps({"first_observed_bottleneck": first_observed_bottleneck, **aggregate}, separators=(",", ":")))


if __name__ == "__main__":
    main()
