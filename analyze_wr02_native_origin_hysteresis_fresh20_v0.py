#!/usr/bin/env python3
"""Aggregate WR-02 vs WR-02+native Origin hysteresis fresh20."""
import json
import statistics
from pathlib import Path

files = sorted(Path("wr02-native-hysteresis-fresh20-artifacts").glob("wr02_native_origin_hysteresis_fresh20_v0_*_seat*.json"))
rows = [json.loads(p.read_text(encoding="utf-8")) for p in files]
if len(rows) != 20:
    raise SystemExit(f"expected 20 results, got {len(rows)}")

ds = [r["delta_self"] for r in rows]
dm = [r["delta_margin"] for r in rows]
current_self = [r["current"]["self"] for r in rows]
candidate_self = [r["candidate"]["self"] for r in rows]
current_margin = [r["current"]["margin"] for r in rows]
candidate_margin = [r["candidate"]["margin"] for r in rows]
delay = [r["candidate"]["telemetry"].get("delayed_switch_turns", 0) for r in rows]
switches = [r["candidate"]["telemetry"].get("confirmed_switches", 0) for r in rows]

out = {
    "schema": "kaggriculture.wr02-native-origin-hysteresis.fresh20.result.v0",
    "battle_count": len(rows),
    "current_absolute_mean_self": statistics.mean(current_self),
    "candidate_absolute_mean_self": statistics.mean(candidate_self),
    "delta_mean_self": statistics.mean(ds),
    "delta_median_self": statistics.median(ds),
    "self_improved": sum(x > 0 for x in ds),
    "self_worsened": sum(x < 0 for x in ds),
    "self_equal": sum(x == 0 for x in ds),
    "min_delta_self": min(ds),
    "max_delta_self": max(ds),
    "current_absolute_mean_margin": statistics.mean(current_margin),
    "candidate_absolute_mean_margin": statistics.mean(candidate_margin),
    "delta_mean_margin": statistics.mean(dm),
    "delta_median_margin": statistics.median(dm),
    "mean_delayed_switch_turns": statistics.mean(delay),
    "mean_confirmed_switches": statistics.mean(switches),
    "cases": [
        {
            "seed": r["seed"],
            "seat": r["seat"],
            "current_self": r["current"]["self"],
            "candidate_self": r["candidate"]["self"],
            "delta_self": r["delta_self"],
            "delta_margin": r["delta_margin"],
            "delayed_switch_turns": r["candidate"]["telemetry"].get("delayed_switch_turns", 0),
            "confirmed_switches": r["candidate"]["telemetry"].get("confirmed_switches", 0),
        }
        for r in rows
    ],
    "boundary": [
        "Fresh independent seeds 8701-8720 with alternating seats.",
        "Only one-turn native Origin switch hysteresis is added to current WR-02.",
        "No post-hoc rescue condition or threshold sweep.",
        "Terminal self is the adoption authority."
    ],
}
Path("wr02_native_origin_hysteresis_fresh20_v0_result.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("WR02_NATIVE_HYSTERESIS_FRESH20_RESULT " + json.dumps(out, ensure_ascii=False, separators=(",", ":")))
