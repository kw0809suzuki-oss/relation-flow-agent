#!/usr/bin/env python3
"""Extract observed decision-boundary candidates from a Judgment probe result.

This is descriptive only:
- it reports where existing controller choices changed,
- it does not claim those boundaries are strategically correct,
- it does not promote them into mainline rules.
"""

import json
import sys
from collections import Counter
from pathlib import Path


def parse_known(items):
    out = {}
    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        out[key] = value
    return out


def transition_candidates(cycles):
    counts = Counter()
    examples = {}
    for left, right in zip(cycles, cycles[1:]):
        a = left["choose"]["selected"]
        b = right["choose"]["selected"]
        if a == b:
            continue
        key = f"{a}->{b}"
        counts[key] += 1

        lk = parse_known(left["observe"]["known"])
        rk = parse_known(right["observe"]["known"])
        changed = {
            k: {"before": lk.get(k), "after": rk.get(k)}
            for k in sorted(set(lk) | set(rk))
            if lk.get(k) != rk.get(k)
        }
        examples.setdefault(key, []).append(changed)

    return {
        key: {
            "count": counts[key],
            "examples": examples[key][:5],
            "status": "observed_boundary_candidate",
            "promote": False,
        }
        for key in sorted(counts)
    }


def identical_state_choice_conflicts(cycles):
    seen = {}
    conflicts = []
    for cycle in cycles:
        known = tuple(sorted(cycle["observe"]["known"]))
        choice = cycle["choose"]["selected"]
        previous = seen.setdefault(known, choice)
        if previous != choice:
            conflicts.append({
                "known": list(known),
                "choices": sorted({previous, choice}),
            })
    return conflicts


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "judgment_probe_result.json")
    data = json.loads(source.read_text())

    result = {
        "schema": "kaggriculture.decision-boundary-observation.v1",
        "source_schema": data.get("schema"),
        "cycle_count": len(data.get("cycles", [])),
        "identical_state_choice_conflicts": identical_state_choice_conflicts(data.get("cycles", [])),
        "transitions": transition_candidates(data.get("cycles", [])),
        "boundary": "descriptive_only_no_rule_promotion",
    }

    out = Path("decision_boundary_observation.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "cycle_count": result["cycle_count"],
        "identical_state_choice_conflict_count": len(result["identical_state_choice_conflicts"]),
        "transition_counts": {k: v["count"] for k, v in result["transitions"].items()},
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
