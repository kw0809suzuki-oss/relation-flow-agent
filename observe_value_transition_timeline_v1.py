#!/usr/bin/env python3
"""Observe the pre-compression Value Transition timeline without mutating the Agent.

Keeps the existing Value Flow coordinate, but preserves consecutive states so a
single match can be read as State_t -> Transition -> State_t+1.
No causal attribution and no policy change.
"""

import json
from pathlib import Path

INPUT = Path("scale_baseline_v1.json")
OUTPUT = Path("value_transition_timeline_v1.json")


def _num(row, key):
    value = row.get(key)
    return value if isinstance(value, (int, float)) else None


def _delta(a, b, key):
    av, bv = _num(a, key), _num(b, key)
    return None if av is None or bv is None else bv - av


def _transition(a, b):
    money_delta = _delta(a, b, "money")
    inventory_delta = _delta(a, b, "produced_value")
    return {
        "from_day": a.get("day"),
        "to_day": b.get("day"),
        "from_state": {
            "money": a.get("money"),
            "land": a.get("land"),
            "hands": a.get("hands"),
            "inventory_value": a.get("produced_value"),
            "collected_value": a.get("collected_value"),
        },
        "observed_change": {
            "money_delta": money_delta,
            "land_delta": _delta(a, b, "land"),
            "hands_delta": _delta(a, b, "hands"),
            "inventory_value_delta": inventory_delta,
            "next_collected_value": b.get("collected_value"),
        },
        "to_state": {
            "money": b.get("money"),
            "land": b.get("land"),
            "hands": b.get("hands"),
            "inventory_value": b.get("produced_value"),
            "collected_value": b.get("collected_value"),
        },
        "descriptive_markers": {
            "money_increased": money_delta is not None and money_delta > 0,
            "inventory_decreased": inventory_delta is not None and inventory_delta < 0,
            "capacity_changed": any(
                d not in (None, 0)
                for d in (_delta(a, b, "land"), _delta(a, b, "hands"))
            ),
        },
    }


def main():
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    cases = []
    for case in payload.get("cases", []):
        obs = case.get("observations", [])
        cases.append({
            "seed": case.get("seed"),
            "seat": case.get("seat"),
            "terminal": case.get("terminal"),
            "transitions": [_transition(a, b) for a, b in zip(obs, obs[1:])],
        })

    out = {
        "schema": "kaggriculture.value-transition-timeline.v1",
        "coordinate": ["capital", "expansion", "operation", "production", "recovery", "terminal"],
        "baseline_identity": payload.get("baseline_identity"),
        "policy_mutated": False,
        "compression": False,
        "cases": cases,
        "boundary": [
            "descriptive observer only; no causal attribution",
            "preserves consecutive observed states instead of reducing each match to aggregate stage metrics",
            "produced_value keeps the exporter meaning and must not be relabeled as production flow",
            "collected_value keeps the exporter meaning and must not be relabeled as sales or profit",
            "Day8-10 is a slice of the same timeline, not a preselected cause window",
            "no implementation candidate is selected by this observer",
        ],
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("VALUE_TRANSITION_TIMELINE_V1 " + json.dumps({
        "case_count": len(cases),
        "transition_count": sum(len(c["transitions"]) for c in cases),
        "policy_mutated": False,
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
