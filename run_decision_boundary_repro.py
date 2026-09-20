#!/usr/bin/env python3
"""Run one additional battle and observe decision-boundary candidates."""

import json
from pathlib import Path

from analyze_decision_boundaries import identical_state_choice_conflicts, transition_candidates
from judgment_trace_bridge import cycles_from_trace
from run_whole_flow_control_v2 import play


SEED = 3206
SEAT = 0


def serialize_cycle(cycle):
    return {
        "observe": {
            "known": list(cycle.observe.known),
            "missing": list(cycle.observe.missing),
        },
        "choose": {
            "selected": cycle.choose.selected,
        },
    }


def main():
    baseline = play(SEED, SEAT, False)
    candidate = play(SEED, SEAT, True)
    cycles = cycles_from_trace({"whole_flow": candidate["flow_trace"]})
    slim = [serialize_cycle(c) for c in cycles]

    result = {
        "schema": "kaggriculture.decision-boundary-repro.v1",
        "seed": SEED,
        "seat": SEAT,
        "baseline_score": baseline["score"],
        "candidate_score": candidate["score"],
        "cycle_count": len(cycles),
        "identical_state_choice_conflicts": identical_state_choice_conflicts(slim),
        "transitions": transition_candidates(slim),
        "boundary": "descriptive_only_no_rule_promotion",
    }

    Path("decision_boundary_repro_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({
        "seed": SEED,
        "seat": SEAT,
        "cycle_count": len(cycles),
        "identical_state_choice_conflict_count": len(result["identical_state_choice_conflicts"]),
        "transition_counts": {k: v["count"] for k, v in result["transitions"].items()},
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
