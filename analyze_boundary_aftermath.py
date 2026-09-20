#!/usr/bin/env python3
"""Observe local aftermath after decision-boundary transitions.

Descriptive only:
- groups boundary transitions,
- measures the next available local relation movement after each transition,
- does not claim causality or strategic correctness,
- never promotes observations into rules.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


AXES = ("money", "capacity", "production")


def parse_known(items):
    out = {}
    for item in items:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        out[key] = value
    return out


def movement_from_cycle(cycle):
    known = parse_known(cycle["observe"]["known"])
    values = {}
    for axis in AXES:
        key = f"movement.{axis}"
        if key not in known:
            return None
        values[axis] = float(known[key])
    return values


def summarize(values):
    if not values:
        return {
            "observed_count": 0,
            "missing_count": 0,
            "mean": None,
            "positive_vote_mean": None,
        }

    means = {
        axis: sum(v[axis] for v in values) / len(values)
        for axis in AXES
    }
    positive_vote_mean = sum(
        sum(v[axis] >= 0.0 for axis in AXES) for v in values
    ) / len(values)
    return {
        "observed_count": len(values),
        "mean": means,
        "positive_vote_mean": positive_vote_mean,
    }


def observe_aftermath(cycles):
    grouped = defaultdict(lambda: {"values": [], "missing": 0, "count": 0})

    for idx in range(1, len(cycles)):
        before = cycles[idx - 1]
        current = cycles[idx]
        a = before["choose"]["selected"]
        b = current["choose"]["selected"]
        if a == b:
            continue

        key = f"{a}->{b}"
        grouped[key]["count"] += 1

        # Use the following cycle as aftermath when available.
        if idx + 1 >= len(cycles):
            grouped[key]["missing"] += 1
            continue

        aftermath = movement_from_cycle(cycles[idx + 1])
        if aftermath is None:
            grouped[key]["missing"] += 1
        else:
            grouped[key]["values"].append(aftermath)

    result = {}
    for key, group in sorted(grouped.items()):
        summary = summarize(group["values"])
        summary["transition_count"] = group["count"]
        summary["missing_count"] = group["missing"]
        summary["status"] = "observed_local_aftermath"
        summary["causal_attribution"] = False
        summary["promote"] = False
        result[key] = summary
    return result


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "judgment_probe_result.json")
    data = json.loads(source.read_text())

    result = {
        "schema": "kaggriculture.decision-boundary-aftermath.v1",
        "source_schema": data.get("schema"),
        "cycle_count": len(data.get("cycles", [])),
        "aftermath": observe_aftermath(data.get("cycles", [])),
        "boundary": "descriptive_only_no_causal_attribution_no_rule_promotion",
    }

    out = Path("decision_boundary_aftermath.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "cycle_count": result["cycle_count"],
        "aftermath": {
            k: {
                "transition_count": v["transition_count"],
                "observed_count": v["observed_count"],
                "missing_count": v["missing_count"],
                "mean": v["mean"],
                "positive_vote_mean": v["positive_vote_mean"],
            }
            for k, v in result["aftermath"].items()
        },
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
