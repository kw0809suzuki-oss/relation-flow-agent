#!/usr/bin/env python3
"""Fresh midgame LAND recovery observation for Scale Chassis v1.

Observer coordinate:
- objective remains terminal score-band improvement
- this experiment only asks whether the observed midgame LAND recovery window repeats
- it does not explain why a particular seed recovers

The baseline agent is unchanged. We observe naturally occurring +1 LAND events
at day >= 8 and measure up to five following days while the added LAND remains.
"""

import json
from pathlib import Path

from export_scale_baseline_v1 import run_case
from scale_roi_observer import ScaleObservation, land_recovery_windows

# Fresh, disjoint from the previous 4092-4101 baseline set.
CASES = [(seed, seed % 2) for seed in range(4102, 4122)]


def main():
    cases = []
    windows = []
    for seed, seat in CASES:
        result = run_case(seed, seat)
        observations = [ScaleObservation(**row) for row in result["observations"]]
        observed = [w for w in land_recovery_windows(observations, max_days=5) if w.start_day >= 8]
        cases.append({
            "seed": seed,
            "seat": seat,
            "terminal": result.get("terminal"),
            "midgame_land_windows": [w.__dict__ for w in observed],
        })
        for w in observed:
            windows.append({"seed": seed, "seat": seat, **w.__dict__})

    positive = [w for w in windows if w["collected_gain"] > 0]
    summary = {
        "fresh_case_count": len(CASES),
        "midgame_land_window_count": len(windows),
        "positive_collection_window_count": len(positive),
        "positive_seed_count": len({w["seed"] for w in positive}),
        "mean_positive_daily_collection": (
            sum(w["daily_collected_gain"] for w in positive) / len(positive)
            if positive else 0.0
        ),
        "interpretation_boundary": (
            "descriptive replication only; do not infer LAND causality or deepen local analysis"
        ),
        "next_decision": (
            "if recovery repeats across multiple fresh seeds, build the minimal timing/remaining-days LAND gate; "
            "otherwise weaken the LAND ROI hypothesis"
        ),
    }
    payload = {
        "schema": "kaggriculture.scale-chassis.land-midgame-recovery.v1",
        "cases": cases,
        "windows": windows,
        "summary": summary,
    }
    Path("land_midgame_recovery_v1.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("LAND_MIDGAME_RECOVERY " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
