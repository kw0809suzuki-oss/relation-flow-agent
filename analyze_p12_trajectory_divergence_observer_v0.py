#!/usr/bin/env python3
"""Find the first daily trajectory point where P12 effects cease to be uniform.

Uses terminal improved/worsened labels only after observation capture, for group
comparison. It does not infer causality and does not modify policy.
"""
import json
import math
import statistics
from pathlib import Path

FILES = sorted(Path("p12-trajectory-observer-artifacts").glob("p12_trajectory_divergence_observer_v0_*_seat*.json"))
ROWS = [json.loads(p.read_text(encoding="utf-8")) for p in FILES]
if len(ROWS) != 20:
    raise SystemExit(f"expected 20 results, got {len(ROWS)}")


def flatten_numeric(obj, prefix=""):
    out = {}
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)) and math.isfinite(float(obj)):
        out[prefix] = float(obj)
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten_numeric(v, p))
    return out


def day_maps(row, day):
    key = str(day)
    cur = row["current"]["days"].get(key)
    cand = row["candidate"]["days"].get(key)
    if cur is None or cand is None:
        return None

    cf = flatten_numeric(cur)
    kf = flatten_numeric(cand)
    common = sorted(set(cf) & set(kf))
    delta = {k: kf[k] - cf[k] for k in common}
    return cf, kf, delta


def group(row):
    d = row["delta_self"]
    return "IMPROVED" if d > 0 else "WORSENED" if d < 0 else "TIED"


def uniq(vals):
    return sorted(set(round(float(v), 9) for v in vals))


def stats(vals):
    if not vals:
        return None
    return {
        "n": len(vals),
        "mean": statistics.mean(vals),
        "median": statistics.median(vals),
        "min": min(vals),
        "max": max(vals),
        "unique": uniq(vals),
    }


days = sorted(set(
    int(d)
    for r in ROWS
    for side in ("current", "candidate")
    for d in r[side]["days"].keys()
))

per_day = {}
first_delta_variation_day = None
first_delta_variation_features = []
first_group_range_separation_day = None
first_group_range_separation_features = []

for day in days:
    records = []
    for r in ROWS:
        maps = day_maps(r, day)
        if maps is None:
            continue
        cf, kf, delta = maps
        records.append({
            "seed": r["seed"],
            "seat": r["seat"],
            "group": group(r),
            "delta_self": r["delta_self"],
            "current": cf,
            "candidate": kf,
            "delta": delta,
        })

    if len(records) != 20:
        per_day[str(day)] = {"case_count": len(records), "complete": False}
        continue

    common_delta_features = sorted(set.intersection(*(set(x["delta"]) for x in records)))
    varying = []
    group_comparisons = {}
    range_separators = []

    for feat in common_delta_features:
        all_vals = [x["delta"][feat] for x in records]
        u = uniq(all_vals)
        if len(u) <= 1:
            continue
        varying.append(feat)

        imp = [x["delta"][feat] for x in records if x["group"] == "IMPROVED"]
        wor = [x["delta"][feat] for x in records if x["group"] == "WORSENED"]
        isep = False
        if imp and wor:
            isep = max(imp) < min(wor) or max(wor) < min(imp)
        group_comparisons[feat] = {
            "all": stats(all_vals),
            "improved": stats(imp),
            "worsened": stats(wor),
            "ranges_disjoint": isep,
        }
        if isep:
            range_separators.append(feat)

    if varying and first_delta_variation_day is None:
        first_delta_variation_day = day
        first_delta_variation_features = varying

    if range_separators and first_group_range_separation_day is None:
        first_group_range_separation_day = day
        first_group_range_separation_features = range_separators

    per_day[str(day)] = {
        "case_count": 20,
        "complete": True,
        "delta_feature_count": len(common_delta_features),
        "varying_delta_feature_count": len(varying),
        "varying_delta_features": varying,
        "range_separator_features": range_separators,
        "group_comparisons": group_comparisons,
    }


# Compact cases for the first informative day.
focus_day = first_delta_variation_day
focus_cases = []
if focus_day is not None:
    focus_feats = first_delta_variation_features
    for r in ROWS:
        cf, kf, delta = day_maps(r, focus_day)
        focus_cases.append({
            "seed": r["seed"],
            "seat": r["seat"],
            "terminal_group": group(r),
            "delta_self": r["delta_self"],
            "delta_margin": r["delta_margin"],
            "delta_features": {f: delta.get(f) for f in focus_feats},
        })


out = {
    "schema": "kaggriculture.p12-trajectory-divergence-observer.fresh20.result.v0",
    "battle_count": len(ROWS),
    "terminal_counts": {
        "improved": sum(group(r) == "IMPROVED" for r in ROWS),
        "worsened": sum(group(r) == "WORSENED" for r in ROWS),
        "tied": sum(group(r) == "TIED" for r in ROWS),
    },
    "observed_days": days,
    "first_delta_variation_day": first_delta_variation_day,
    "first_delta_variation_features": first_delta_variation_features,
    "first_group_range_separation_day": first_group_range_separation_day,
    "first_group_range_separation_features": first_group_range_separation_features,
    "focus_cases": focus_cases,
    "per_day": per_day,
    "boundary": [
        "Observation-only paired replay; no policy mutation.",
        "first_delta_variation_day means the earliest day when candidate-current numeric State delta is not identical across all 20 cases.",
        "range separation is descriptive association with terminal improved/worsened groups, not a causal trigger.",
        "No feature is promoted into policy from this result alone.",
    ],
}

Path("p12_trajectory_divergence_observer_v0_result.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("P12_TRAJECTORY_DIVERGENCE_RESULT " + json.dumps({
    "battle_count": out["battle_count"],
    "first_delta_variation_day": first_delta_variation_day,
    "first_delta_variation_features": first_delta_variation_features,
    "first_group_range_separation_day": first_group_range_separation_day,
    "first_group_range_separation_features": first_group_range_separation_features,
}, separators=(",", ":")))
