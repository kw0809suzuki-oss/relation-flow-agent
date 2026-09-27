#!/usr/bin/env python3
"""Aggregate observation-only P12 trigger diagnostics across Fresh20."""
import json
import statistics
from pathlib import Path

FILES = sorted(Path("p12-trigger-observer-artifacts").glob("p12_trigger_observer_v0_*_seat*.json"))
ROWS = [json.loads(p.read_text(encoding="utf-8")) for p in FILES]
if len(ROWS) != 20:
    raise SystemExit(f"expected 20 results, got {len(ROWS)}")


def getpath(row, *path, default=0):
    cur = row
    for key in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return default
    return default if cur is None else cur


def feature_row(r):
    cur_dup = getpath(r, "current", "day0_summary", "duplicate_plant_requests")
    cand_dup = getpath(r, "candidate", "day0_summary", "duplicate_plant_requests")
    cur_plant = getpath(r, "current", "day0_summary", "plant_request_count")
    cand_plant = getpath(r, "candidate", "day0_summary", "plant_request_count")
    d1 = r.get("day1_candidate_minus_current") or {}
    d1_tiles = d1.get("tile_counts") or {}
    d1_seeds = d1.get("seeds") or {}
    return {
        "seed": r["seed"],
        "seat": r["seat"],
        "delta_self": r["delta_self"],
        "delta_margin": r["delta_margin"],
        "terminal_group": "IMPROVED" if r["delta_self"] > 0 else ("WORSENED" if r["delta_self"] < 0 else "TIED"),
        "day0_current_duplicate_plant_requests": cur_dup,
        "day0_candidate_duplicate_plant_requests": cand_dup,
        "day0_delta_duplicate_plant_requests": cand_dup - cur_dup,
        "day0_current_plant_requests": cur_plant,
        "day0_candidate_plant_requests": cand_plant,
        "day0_delta_plant_requests": cand_plant - cur_plant,
        "day0_changed_turn_count": r.get("day0_changed_turn_count", 0),
        "day1_delta_money": d1.get("money"),
        "day1_delta_hands_count": d1.get("hands_count"),
        "day1_delta_occupied_unlocked": d1_tiles.get("occupied_unlocked"),
        "day1_delta_empty_unlocked": d1_tiles.get("empty_unlocked"),
        "day1_delta_plant_tiles": d1_tiles.get("plant_tiles"),
        "day1_delta_animal_tiles": d1_tiles.get("animal_tiles"),
        "day1_delta_melon_seed": d1_seeds.get("MELON"),
        "day1_delta_wheat_seed": d1_seeds.get("WHEAT"),
        "first_changed_turn": (
            {
                "day": r["day0_changed_turns"][0]["day"],
                "hour": r["day0_changed_turns"][0]["hour"],
                "current_plant_requests": r["day0_changed_turns"][0]["current_action"]["plant_requests"],
                "candidate_plant_requests": r["day0_changed_turns"][0]["candidate_action"]["plant_requests"],
            }
            if r.get("day0_changed_turns")
            else None
        ),
    }


FEATURES = [feature_row(r) for r in ROWS]


NUMERIC = [
    "delta_self",
    "delta_margin",
    "day0_current_duplicate_plant_requests",
    "day0_candidate_duplicate_plant_requests",
    "day0_delta_duplicate_plant_requests",
    "day0_current_plant_requests",
    "day0_candidate_plant_requests",
    "day0_delta_plant_requests",
    "day0_changed_turn_count",
    "day1_delta_money",
    "day1_delta_hands_count",
    "day1_delta_occupied_unlocked",
    "day1_delta_empty_unlocked",
    "day1_delta_plant_tiles",
    "day1_delta_animal_tiles",
    "day1_delta_melon_seed",
    "day1_delta_wheat_seed",
]


def summarize(rows):
    out = {"count": len(rows)}
    for k in NUMERIC:
        vals = [x[k] for x in rows if isinstance(x.get(k), (int, float))]
        if vals:
            out[k] = {
                "mean": statistics.mean(vals),
                "median": statistics.median(vals),
                "min": min(vals),
                "max": max(vals),
            }
    return out


improved = [x for x in FEATURES if x["terminal_group"] == "IMPROVED"]
worsened = [x for x in FEATURES if x["terminal_group"] == "WORSENED"]
tied = [x for x in FEATURES if x["terminal_group"] == "TIED"]

cross_tabs = {
    "baseline_had_duplicate_plant_requests": {
        "yes_improved": sum(x["day0_current_duplicate_plant_requests"] > 0 and x["terminal_group"] == "IMPROVED" for x in FEATURES),
        "yes_worsened": sum(x["day0_current_duplicate_plant_requests"] > 0 and x["terminal_group"] == "WORSENED" for x in FEATURES),
        "no_improved": sum(x["day0_current_duplicate_plant_requests"] == 0 and x["terminal_group"] == "IMPROVED" for x in FEATURES),
        "no_worsened": sum(x["day0_current_duplicate_plant_requests"] == 0 and x["terminal_group"] == "WORSENED" for x in FEATURES),
    },
    "p12_reduced_duplicate_plant_requests": {
        "yes_improved": sum(x["day0_delta_duplicate_plant_requests"] < 0 and x["terminal_group"] == "IMPROVED" for x in FEATURES),
        "yes_worsened": sum(x["day0_delta_duplicate_plant_requests"] < 0 and x["terminal_group"] == "WORSENED" for x in FEATURES),
        "no_improved": sum(x["day0_delta_duplicate_plant_requests"] >= 0 and x["terminal_group"] == "IMPROVED" for x in FEATURES),
        "no_worsened": sum(x["day0_delta_duplicate_plant_requests"] >= 0 and x["terminal_group"] == "WORSENED" for x in FEATURES),
    },
    "day1_plant_tiles_increased": {
        "yes_improved": sum((x["day1_delta_plant_tiles"] or 0) > 0 and x["terminal_group"] == "IMPROVED" for x in FEATURES),
        "yes_worsened": sum((x["day1_delta_plant_tiles"] or 0) > 0 and x["terminal_group"] == "WORSENED" for x in FEATURES),
        "no_improved": sum((x["day1_delta_plant_tiles"] or 0) <= 0 and x["terminal_group"] == "IMPROVED" for x in FEATURES),
        "no_worsened": sum((x["day1_delta_plant_tiles"] or 0) <= 0 and x["terminal_group"] == "WORSENED" for x in FEATURES),
    },
}

out = {
    "schema": "kaggriculture.p12-trigger-observer.fresh20.result.v0",
    "battle_count": len(FEATURES),
    "terminal_counts": {
        "improved": len(improved),
        "worsened": len(worsened),
        "tied": len(tied),
    },
    "group_summary": {
        "improved": summarize(improved),
        "worsened": summarize(worsened),
        "tied": summarize(tied) if tied else {"count": 0},
    },
    "cross_tabs": cross_tabs,
    "cases": FEATURES,
    "boundary": [
        "Observation-only association scan on the already-existing WR-02 vs WR-02+P12 Fresh20 comparison.",
        "No feature here is treated as a causal trigger.",
        "duplicate_plant_requests counts same-turn PLANT requests whose actors occupy the same current tile.",
        "occupied_unlocked is an observable non-null/non-LOCKED count, not a semantic productive-value score.",
        "The purpose is to identify the next discriminating observation, not to adopt P12.",
    ],
}

Path("p12_trigger_observer_v0_result.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print("P12_TRIGGER_OBSERVER_RESULT " + json.dumps(out, ensure_ascii=False, separators=(",", ":")))
