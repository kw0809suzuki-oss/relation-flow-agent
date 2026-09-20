#!/usr/bin/env python3
"""Contrast paired boundary aftermath without causal claims."""

import json
import sys
from pathlib import Path


PAIRS = (
    ("maintain->switch", "switch->maintain"),
    ("maintain->push", "push->maintain"),
    ("switch->push", "push->switch"),
)


def delta(a, b):
    if a is None or b is None:
        return None
    return {k: a[k] - b[k] for k in a}


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "decision_boundary_aftermath.json")
    data = json.loads(source.read_text())
    aftermath = data["aftermath"]

    contrasts = {}
    for left, right in PAIRS:
        if left not in aftermath or right not in aftermath:
            continue
        a, b = aftermath[left], aftermath[right]
        contrasts[f"{left}__vs__{right}"] = {
            "left_count": a["observed_count"],
            "right_count": b["observed_count"],
            "mean_delta_left_minus_right": delta(a["mean"], b["mean"]),
            "positive_vote_mean_delta": (
                a["positive_vote_mean"] - b["positive_vote_mean"]
                if a["positive_vote_mean"] is not None and b["positive_vote_mean"] is not None
                else None
            ),
            "status": "descriptive_contrast_only",
            "causal_attribution": False,
            "promote": False,
        }

    result = {
        "schema": "kaggriculture.decision-boundary-aftermath-contrast.v1",
        "contrasts": contrasts,
        "boundary": "descriptive_only_no_causal_attribution_no_rule_promotion",
    }
    Path("decision_boundary_aftermath_contrast.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
