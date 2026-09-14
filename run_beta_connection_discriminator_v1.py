#!/usr/bin/env python3
"""Targeted post-hoc observation for the six seeds where beta connection changed terminal margin.

Purpose: do not invent new features. Re-run the unchanged observation lens on the
six affected seeds and inspect the already-defined Relation windows at beta-stop.
The improved/worsened labels are attached only after observation extraction.
"""

import json
from pathlib import Path

from run_pattern_mining_v1 import play
from run_pattern_validation_v1 import component_events

CASES = (
    (3366, 0, "improved", 20006.0),
    (3367, 1, "worsened", -3844.0),
    (3373, 1, "worsened", -1375.0),
    (3375, 1, "improved", 21893.0),
    (3400, 0, "worsened", -3597.0),
    (3406, 0, "improved", 3916.0),
)


def compact_beta(events):
    out = []
    for row in events["beta_stop"]:
        out.append({
            "step": row["step"],
            "active_relation": row.get("active_relation"),
            "cow_relation": row.get("cow_relation"),
        })
    return out


def main():
    rows = []
    for seed, seat, label, margin_delta in CASES:
        c = play(seed, seat)
        events = component_events(c["pattern_bundle"])
        # Outcome label is attached only after result-blind observation extraction.
        rows.append({
            "seed": seed,
            "seat": seat,
            "beta_stop": compact_beta(events),
            "alpha_slowdown": events["alpha_slowdown"],
            "alpha_restart": events["alpha_restart"],
            "connection_outcome": label,
            "margin_delta": margin_delta,
        })

    result = {
        "schema": "kaggriculture.beta-connection-discriminator.v1",
        "question": "within the six seeds where beta connection changed actions and terminal, do already-defined Relation windows distinguish improved from worsened cases?",
        "observation_definitions_changed": False,
        "new_features_added": False,
        "terminal_used_during_observation": False,
        "cases": rows,
    }
    Path("beta_connection_discriminator_v1.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print("BETA_CONNECTION_DISCRIMINATOR " + json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
