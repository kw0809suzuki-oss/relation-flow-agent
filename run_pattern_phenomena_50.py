#!/usr/bin/env python3
"""Observe 50 fresh matches as whole phenomena using frozen alpha/beta components.

Component definitions are imported from the validated fixed-component lens.
Terminal score is attached only after component extraction and is used for
post-hoc comparison, never to define the components.
"""

import json
from pathlib import Path
from statistics import mean, median

from run_pattern_mining_v1 import play
from run_pattern_validation_v1 import component_events

CASES = tuple((seed, (seed - 3312) % 2) for seed in range(3312, 3362))


def event_sequence(events):
    rows = []
    for name, items in events.items():
        for item in items:
            rows.append({
                "step": item["step"],
                "component": name,
                "active_relation": item.get("active_relation"),
                "cow_relation": item.get("cow_relation"),
            })
    return sorted(rows, key=lambda x: (x["step"], x["component"]))


def main():
    cases = []
    for seed, seat in CASES:
        c = play(seed, seat)
        events = component_events(c["pattern_bundle"])
        c["fixed_component_events"] = events
        c["phenomenon_sequence"] = event_sequence(events)
        cases.append(c)

    margins = [c["terminal"]["margin"] for c in cases]
    wins = sum(1 for c in cases if c["terminal"]["win"])

    component_event_counts = {
        name: sum(len(c["fixed_component_events"][name]) for c in cases)
        for name in ("alpha_slowdown", "alpha_restart", "beta_stop")
    }
    component_trajectory_counts = {
        name: sum(bool(c["fixed_component_events"][name]) for c in cases)
        for name in ("alpha_slowdown", "alpha_restart", "beta_stop")
    }

    summary = {
        "case_count": len(cases),
        "seed_range": "3312-3361",
        "component_event_counts": component_event_counts,
        "component_trajectory_counts": component_trajectory_counts,
        "wins": wins,
        "mean_margin": mean(margins),
        "median_margin": median(margins),
        "best_margin": max(margins),
        "worst_margin": min(margins),
        "definitions_frozen_before_batch": True,
        "terminal_used_to_define_components": False,
        "control_added": False,
    }

    result = {
        "schema": "kaggriculture.relation-flow-phenomena50.v1",
        "purpose": "increase the number of whole-match phenomena observed with the frozen alpha/beta lens, then brush up the observation representation",
        "source_component_batch": "3264-3287",
        "external_validation_batch": "3288-3311",
        "observation_seed_range": "3312-3361",
        "cases": cases,
        "summary": summary,
    }

    out = Path("pattern_phenomena_50_3312_3361.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("PHENOMENA_50 " + json.dumps(summary, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
