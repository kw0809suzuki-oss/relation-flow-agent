#!/usr/bin/env python3
"""Outside-in capital-cycle observer.

No policy mutation and no Master/Flow labels. Re-read the existing 12 cases as
whole waterways: capital -> capacity bundle -> asset stock -> liquidation ->
next bundle -> terminal. The purpose is descriptive comparison of high vs low
terminal cases, not causal attribution or a new Bundle theory.
"""
import json
from pathlib import Path

SRC = Path("scale_baseline_v1.json")
OUT = Path("capital_cycle_v1.json")


def analyze(case):
    rows = case["observations"]
    cycles = []
    liquidations = []
    expansions = []
    stock_peaks = []

    for prev, cur in zip(rows, rows[1:]):
        dm = cur["money"] - prev["money"]
        ds = cur["produced_value"] - prev["produced_value"]
        bundle = {
            "land": cur["land"] - prev["land"],
            "hands": cur["hands"] - prev["hands"],
            "animals": (cur.get("animals") or 0) - (prev.get("animals") or 0),
        }
        expanded = any(v > 0 for v in bundle.values())
        liquidation = dm > 0 and ds < 0
        if expanded:
            expansions.append({"day": cur["day"], "bundle_delta": bundle, "money": cur["money"], "stock": cur["produced_value"]})
        if liquidation:
            liquidations.append({"day": cur["day"], "money_gain": dm, "stock_drop": -ds, "money": cur["money"], "stock": cur["produced_value"]})
        if cur["produced_value"] > prev["produced_value"]:
            stock_peaks.append({"day": cur["day"], "stock_gain": ds, "stock": cur["produced_value"]})

    # A descriptive cycle starts at liquidation and asks whether capacity expands
    # and harvested-product stock subsequently rises before the next liquidation.
    for i, liq in enumerate(liquidations):
        end_day = liquidations[i + 1]["day"] if i + 1 < len(liquidations) else 31
        exp = next((e for e in expansions if liq["day"] <= e["day"] < end_day), None)
        stock = next((s for s in stock_peaks if liq["day"] < s["day"] <= end_day), None)
        cycles.append({
            "liquidation_day": liq["day"],
            "money_gain": liq["money_gain"],
            "next_expansion_day": exp["day"] if exp else None,
            "next_expansion_bundle": exp["bundle_delta"] if exp else None,
            "next_stock_rise_day": stock["day"] if stock else None,
            "next_stock_gain": stock["stock_gain"] if stock else None,
            "reconnected": bool(exp and stock),
        })

    terminal = case["terminal"]["self"]
    return {
        "seed": case["seed"], "seat": case["seat"], "terminal": case["terminal"],
        "liquidation_count": len(liquidations),
        "expansion_count": len(expansions),
        "reconnected_cycles": sum(c["reconnected"] for c in cycles),
        "total_liquidation_gain": sum(x["money_gain"] for x in liquidations),
        "max_stock": max((r["produced_value"] for r in rows), default=0),
        "peak_land": max((r["land"] for r in rows), default=0),
        "peak_hands": max((r["hands"] for r in rows), default=0),
        "peak_animals": max(((r.get("animals") or 0) for r in rows), default=0),
        "cycles": cycles,
    }


def main():
    data = json.loads(SRC.read_text())
    cases = [analyze(c) for c in data["cases"]]
    ranked = sorted(cases, key=lambda c: c["terminal"]["self"], reverse=True)
    n = len(ranked)
    high = ranked[: n // 3]
    low = ranked[-(n // 3):]

    def group(rows):
        def mean(key):
            return sum(r[key] for r in rows) / len(rows) if rows else None
        return {
            "count": len(rows),
            "mean_terminal_self": sum(r["terminal"]["self"] for r in rows) / len(rows) if rows else None,
            "mean_liquidations": mean("liquidation_count"),
            "mean_expansions": mean("expansion_count"),
            "mean_reconnected_cycles": mean("reconnected_cycles"),
            "mean_total_liquidation_gain": mean("total_liquidation_gain"),
            "mean_max_stock": mean("max_stock"),
            "mean_peak_land": mean("peak_land"),
            "mean_peak_hands": mean("peak_hands"),
            "mean_peak_animals": mean("peak_animals"),
            "seeds": [r["seed"] for r in rows],
        }

    out = {
        "coordinate": "money -> investment/capacity bundle -> asset stock -> liquidation -> next bundle -> terminal",
        "policy_mutated": False,
        "boundary": "descriptive only; high/low terminal comparison does not establish causality",
        "cases_ranked_by_terminal": ranked,
        "high_terminal_top_third": group(high),
        "low_terminal_bottom_third": group(low),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("CAPITAL_CYCLE_V1 " + json.dumps({
        "high": out["high_terminal_top_third"],
        "low": out["low_terminal_bottom_third"],
    }, separators=(",", ":")))

if __name__ == "__main__":
    main()
