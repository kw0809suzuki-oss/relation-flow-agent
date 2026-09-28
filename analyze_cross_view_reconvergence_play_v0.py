#!/usr/bin/env python3
"""Re-convergence Playground v0.

Exploratory observer over Cross-View Timeline v0.

It asks only:
- when did the compact Difference View become non-empty?
- which observed domains appeared while the difference was open?
- did the compact View return to empty?
- where did the last observed non-empty run begin?

No causal claim, strength claim, or policy recommendation is emitted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Set

import cross_view_timeline_v0 as cv

PRODUCTIVE_DOMAINS = {
    "seed_total",
    "seeds",
    "plant_count",
    "plants",
    "animal_count",
    "animals",
    "yield_units_total",
    "yield",
}


def timestamp(row: Mapping[str, Any]) -> Dict[str, int]:
    return {
        "step_index": int(row["step_index"]),
        "day": int(row["day"]),
        "hour": int(row["hour"]),
    }


def difference_domains(row: Mapping[str, Any]) -> Set[str]:
    view = row["difference_view"]
    out = set((view.get("scalar_delta") or {}).keys())
    out.update((view.get("composition_delta") or {}).keys())
    return out


def equality_runs(timeline: List[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    if not timeline:
        return []
    flags = [bool(r["difference_view"]["view_difference_empty"]) for r in timeline]
    runs = []
    start = 0
    value = flags[0]
    for idx in range(1, len(flags) + 1):
        if idx == len(flags) or flags[idx] != value:
            runs.append(
                {
                    "start_step": start,
                    "end_step": idx - 1,
                    "duration_turns": idx - start,
                    "difference_view_empty": value,
                    "start_timestamp": timestamp(timeline[start]),
                    "end_timestamp": timestamp(timeline[idx - 1]),
                }
            )
            if idx < len(flags):
                start = idx
                value = flags[idx]
    return runs


def domain_introductions(
    timeline: List[Mapping[str, Any]], start: int, end: int
) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out = []
    for row in timeline[start : end + 1]:
        domains = difference_domains(row)
        new = sorted(domains - seen)
        if new:
            out.append(
                {
                    "timestamp": timestamp(row),
                    "new_domains": new,
                    "scalar_delta": row["difference_view"].get("scalar_delta") or {},
                    "composition_delta": row["difference_view"].get("composition_delta")
                    or {},
                }
            )
        seen.update(domains)
    return out


def direct_witness_kinds(
    timeline: List[Mapping[str, Any]], start: int, end: int
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in timeline[start : end + 1]:
        for p in row["players"]:
            tr = p.get("transition_from_previous_step") or {}
            for w in tr.get("direct_witnesses", []) or []:
                k = str(w.get("kind"))
                counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items()))


def analyze_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    timeline = list(payload["timeline"])
    runs = equality_runs(timeline)
    transient = []
    for idx, run in enumerate(runs):
        if run["difference_view_empty"]:
            continue
        if idx + 1 < len(runs) and runs[idx + 1]["difference_view_empty"]:
            introductions = domain_introductions(
                timeline, run["start_step"], run["end_step"]
            )
            all_domains = sorted(
                {
                    d
                    for z in introductions
                    for d in z["new_domains"]
                }
            )
            transient.append(
                {
                    **run,
                    "reconvergence_timestamp": runs[idx + 1]["start_timestamp"],
                    "domain_introductions": introductions,
                    "observed_domains": all_domains,
                    "productive_domain_observed": bool(
                        set(all_domains) & PRODUCTIVE_DOMAINS
                    ),
                    "direct_witness_counts": direct_witness_kinds(
                        timeline, run["start_step"], run["end_step"]
                    ),
                }
            )

    final_nonempty = None
    if runs and not runs[-1]["difference_view_empty"]:
        r = runs[-1]
        introductions = domain_introductions(
            timeline, r["start_step"], r["end_step"]
        )
        final_nonempty = {
            **r,
            "domain_introductions": introductions,
            "direct_witness_counts": direct_witness_kinds(
                timeline, r["start_step"], r["end_step"]
            ),
            "boundary": (
                "This run remains non-empty through the recorded terminal only in "
                "the compact Difference View. It is not a claim of irreversible "
                "causal divergence."
            ),
        }

    short_runs = [
        r
        for r in runs
        if r["duration_turns"] <= 3
    ]

    return {
        "schema": "kaggriculture.cross-view-reconvergence-playground.v0",
        "source": payload["source"],
        "runs": runs,
        "transient_divergence_runs": transient,
        "final_nonempty_run": final_nonempty,
        "short_run_flickers": short_runs,
        "observations": {
            "reconvergence_after_productive_difference_count": sum(
                1 for x in transient if x["productive_domain_observed"]
            ),
            "transient_divergence_count": len(transient),
            "difference_empty_run_count": sum(
                1 for r in runs if r["difference_view_empty"]
            ),
            "difference_nonempty_run_count": sum(
                1 for r in runs if not r["difference_view_empty"]
            ),
        },
        "boundary": [
            "Difference View is the compact Cross-View Timeline projection, not full hidden state.",
            "A return to empty means re-convergence only in this View.",
            "Productive-domain appearance does not imply a durable residual.",
            "A final non-empty run through terminal does not establish causality or strategic importance.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("replay", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    timeline = cv.build(replay)
    result = analyze_payload(timeline)
    out = args.out or args.replay.with_name(
        args.replay.stem + "_cross_view_reconvergence_play_v0.json"
    )
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "source": result["source"],
                "observations": result["observations"],
                "final_nonempty_start": (
                    result["final_nonempty_run"]["start_timestamp"]
                    if result["final_nonempty_run"]
                    else None
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
