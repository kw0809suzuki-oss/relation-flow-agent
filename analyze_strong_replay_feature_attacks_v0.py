#!/usr/bin/env python3
"""Strong Replay Feature Attacks v0.

Consumes one or more Cross-View Timeline v0 JSON files and extracts only
external observations useful for later model design.

No policy mutation. No strength score. No causal promotion.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def witnesses(row, player):
    tr = row["players"][player].get("transition_from_previous_step") or {}
    return tr.get("direct_witnesses", []) or []


def successful_conversion_rows(timeline, player, subtype=None):
    out = []
    for row in timeline[1:]:
        for w in witnesses(row, player):
            if w.get("kind") != "productive_conversion":
                continue
            if subtype is not None and w.get("subtype") != subtype:
                continue
            out.append((row, w))
    return out


def first_durable_recovery(timeline, player, threshold):
    cash = [float(r["players"][player]["state"]["cash"]) for r in timeline]
    for idx in range(1, len(cash)):
        if cash[idx] >= threshold and all(v >= threshold for v in cash[idx:]):
            return {
                "step": idx,
                "day": timeline[idx]["day"],
                "hour": timeline[idx]["hour"],
                "cash": cash[idx],
            }
    return None


def lineage_stats(timeline, player, min_planted_day=20):
    activated = {}
    first_output = {}
    harvested = set()

    for row in timeline[1:]:
        for w in witnesses(row, player):
            kind = w.get("kind")
            if kind == "productive_state_activated":
                asset = w.get("asset") or {}
                if asset.get("kind") == "PLANT":
                    activated[w["lineage_key"]] = {
                        "step": row["step_index"],
                        "day": row["day"],
                        "hour": row["hour"],
                        "crop": asset.get("crop"),
                        "planted_day": int(asset.get("planted_day", row["day"])),
                    }
            elif kind == "output_formed":
                first_output.setdefault(w.get("lineage_key"), row["step_index"])
            elif kind == "harvest_boundary":
                for tile in w.get("tiles", []) or []:
                    if tile.get("lineage_key"):
                        harvested.add(tile["lineage_key"])

    selected = {
        k: v
        for k, v in activated.items()
        if v["planted_day"] >= min_planted_day
    }
    by_day = defaultdict(lambda: {"activated": 0, "output": 0, "harvested": 0})
    by_crop = defaultdict(lambda: {"activated": 0, "output": 0, "harvested": 0})
    output_lags = defaultdict(list)

    for key, a in selected.items():
        d = a["planted_day"]
        crop = a["crop"]
        by_day[d]["activated"] += 1
        by_crop[crop]["activated"] += 1
        if key in first_output:
            by_day[d]["output"] += 1
            by_crop[crop]["output"] += 1
            output_lags[crop].append(first_output[key] - a["step"])
        if key in harvested:
            by_day[d]["harvested"] += 1
            by_crop[crop]["harvested"] += 1

    return {
        "min_planted_day": min_planted_day,
        "activated": len(selected),
        "with_output": sum(1 for k in selected if k in first_output),
        "harvested": sum(1 for k in selected if k in harvested),
        "by_day": {str(k): v for k, v in sorted(by_day.items())},
        "by_crop": dict(sorted(by_crop.items())),
        "first_output_lag_by_crop": {
            crop: {
                "count": len(xs),
                "median_turns": statistics.median(xs),
                "max_turns": max(xs),
            }
            for crop, xs in sorted(output_lags.items())
            if xs
        },
    }


def analyze_player(payload, player):
    tl = payload["timeline"]
    conversions = {}
    for subtype in ("LAND", "ANIMAL", "SEED", "HIRE"):
        rows = successful_conversion_rows(tl, player, subtype)
        after14 = [r for r, _ in rows if int(r["day"]) >= 14]
        after20 = [r for r, _ in rows if int(r["day"]) >= 20]
        conversions[subtype] = {
            "count": len(rows),
            "after_day14": len(after14),
            "after_day20": len(after20),
            "last": (
                {
                    "step": rows[-1][0]["step_index"],
                    "day": rows[-1][0]["day"],
                    "hour": rows[-1][0]["hour"],
                }
                if rows
                else None
            ),
        }

    return {
        "agent": payload["source"]["agents"][player],
        "reward": payload["source"]["rewards"][player],
        "durable_initial_cash_recovery": first_durable_recovery(tl, player, 3000),
        "productive_conversion": conversions,
        "late_crop_lineage": lineage_stats(tl, player, min_planted_day=20),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timelines", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    episodes = []
    for path in args.timelines:
        payload = json.loads(path.read_text(encoding="utf-8"))
        episodes.append({
            "source": payload["source"],
            "players": [analyze_player(payload, 0), analyze_player(payload, 1)],
        })

    all_players = [p for e in episodes for p in e["players"]]
    paybacks = [p["durable_initial_cash_recovery"] for p in all_players]
    late = [p["late_crop_lineage"] for p in all_players]

    aggregate = {
        "player_instances": len(all_players),
        "durable_payback_timestamps": Counter(
            (
                f"D{x['day']}h{x['hour']}"
                if x is not None
                else "NONE"
            )
            for x in paybacks
        ),
        "after_day14_conversion_totals": {
            subtype: sum(
                p["productive_conversion"][subtype]["after_day14"]
                for p in all_players
            )
            for subtype in ("LAND", "ANIMAL", "SEED", "HIRE")
        },
        "after_day20_conversion_totals": {
            subtype: sum(
                p["productive_conversion"][subtype]["after_day20"]
                for p in all_players
            )
            for subtype in ("LAND", "ANIMAL", "SEED", "HIRE")
        },
        "late_crop_activated": sum(x["activated"] for x in late),
        "late_crop_with_output": sum(x["with_output"] for x in late),
        "late_crop_harvested": sum(x["harvested"] for x in late),
        "late_crop_types": sorted({
            crop
            for x in late
            for crop in x["by_crop"].keys()
        }),
    }

    result = {
        "schema": "kaggriculture.strong-replay-feature-attacks.v0",
        "episodes": episodes,
        "aggregate": aggregate,
        "boundary": [
            "Durable initial-cash recovery is an external timestamp, not an adopted target.",
            "Successful conversion uses Cross-View direct witnesses only.",
            "Late crop lineage follows physical crop lineage keys; it does not attribute profit.",
            "Observed action-class timing is not promoted to an optimal cutoff.",
            "No feature in this report is a strength score.",
        ],
    }

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
