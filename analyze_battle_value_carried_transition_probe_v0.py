#!/usr/bin/env python3
"""Aggregate Carried Transition Probe v0 artifacts without mechanism labels."""
import glob
import json
from collections import Counter
from pathlib import Path

FOCUS = ("STRAWBERRY", "MELON", "WOOL")

def mean(xs):
    return sum(xs) / len(xs) if xs else None

def main():
    paths = sorted(Path(p) for p in glob.glob(
        "carried-transition-artifacts/**/battle_value_carried_transition_probe_v0_*.json",
        recursive=True,
    ))
    if len(paths) != 5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}: {paths}")

    raws = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    cases = []
    exact_path_frequency = Counter()
    exact_path_frequency_by_side = {"self": Counter(), "opponent": Counter()}

    for raw in raws:
        seat = int(raw["seat"])
        item_counts = {item: 0 for item in FOCUS}
        strawberry_events = []

        for e in raw["events"]:
            item = e["item"]
            item_counts[item] += 1
            if item != "STRAWBERRY":
                continue

            # raw_diff entries are indexed by player observation 0/1.
            self_diff = e["raw_diff_by_player_observation"][seat]
            opp_diff = e["raw_diff_by_player_observation"][1 - seat]
            self_paths = [d["path"] for d in self_diff]
            opp_paths = [d["path"] for d in opp_diff]

            for p in set(self_paths + opp_paths):
                exact_path_frequency[p] += 1
            for p in self_paths:
                exact_path_frequency_by_side["self"][p] += 1
            for p in opp_paths:
                exact_path_frequency_by_side["opponent"][p] += 1

            strawberry_events.append({
                "from": e["from"],
                "to": e["to"],
                "carried_residual_before": e["carried_residual_before"],
                "carried_residual_after": e["carried_residual_after"],
                "carried_residual_delta": e["carried_residual_delta"],
                "position_before": e["position_before"],
                "position_after": e["position_after"],
                "self_raw_diff": self_diff,
                "opponent_raw_diff": opp_diff,
            })

        cases.append({
            "seed": raw["seed"],
            "seat": seat,
            "terminal": raw["terminal"],
            "event_counts": item_counts,
            "strawberry_events": strawberry_events,
        })

    terminals_self = [float(c["terminal"]["self"]) for c in cases]
    terminals_opp = [float(c["terminal"]["opponent"]) for c in cases]
    payload = {
        "schema": "kaggriculture.strong-origin-v2.carried-transition-probe.result.v0",
        "battle_count": 5,
        "terminal_absolute": {
            "mean_self": mean(terminals_self),
            "mean_opponent": mean(terminals_opp),
            "mean_margin": mean([s - o for s, o in zip(terminals_self, terminals_opp)]),
        },
        "event_count_mean": {
            item: mean([c["event_counts"][item] for c in cases])
            for item in FOCUS
        },
        "strawberry_exact_changed_path_frequency": [
            {"path": path, "event_count": count}
            for path, count in exact_path_frequency.most_common()
        ],
        "strawberry_exact_changed_path_frequency_by_side": {
            side: [
                {"path": path, "event_count": count}
                for path, count in counter.most_common()
            ]
            for side, counter in exact_path_frequency_by_side.items()
        },
        "cases": cases,
        "boundary": [
            "Only STRAWBERRY trigger events carry full raw diffs in this compact result.",
            "MELON and WOOL are retained only as event-count positive controls.",
            "A changed path is a simultaneous field difference across one market-after -> next market-before interval, not a causal attribution.",
            "Exact path frequency is a count of repeated JSON path changes only; it does not name or classify a mechanism.",
            "No HARVEST, DROP, maturity, movement, transfer, production, item lineage, Action, policy, Direction, Candidate, or adoption conclusion is inferred.",
        ],
    }
    Path("battle_value_carried_transition_probe_v0_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("BATTLE_VALUE_CARRIED_TRANSITION_RESULT " + json.dumps({
        "terminal_absolute": payload["terminal_absolute"],
        "event_count_mean": payload["event_count_mean"],
        "strawberry_event_counts": {
            str(c["seed"]): c["event_counts"]["STRAWBERRY"] for c in cases
        },
    }, ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
