#!/usr/bin/env python3
"""Aggregate the Day3 Hour0 first-divergence action replacement."""
import glob
import json
from pathlib import Path

OUT = Path("p12_day3h0_action_replacement_v0_result.json")


def original_group(delta):
    if delta > 0:
        return "improved"
    if delta < 0:
        return "worsened"
    return "equal"


def stats(values):
    if not values:
        return None
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "nonzero": sum(1 for x in values if x != 0),
    }


def main():
    files = sorted(glob.glob("p12-day3h0-replacement-artifacts/*.json"))
    cases = [json.loads(Path(p).read_text(encoding="utf-8")) for p in files]

    rows = []
    for c in cases:
        q = c["comparisons"]
        rows.append({
            "seed": c["seed"],
            "seat": c["seat"],
            "original_group": original_group(float(q["normal_delta_self"])),
            "action_changed": bool(c["replacement"]["action_changed"]),
            **q,
        })

    changed = [r for r in rows if r["action_changed"]]
    unchanged = [r for r in rows if not r["action_changed"]]

    by_group = {}
    for group in ("improved", "worsened", "equal"):
        rs = [r for r in rows if r["original_group"] == group]
        crs = [r for r in rs if r["action_changed"]]
        by_group[group] = {
            "n": len(rs),
            "action_changed_n": len(crs),
            "h1_inventory_response_n": sum(
                1 for r in crs
                if r["replaced_h1_inventory_delta"] != r["normal_h1_inventory_delta"]
            ),
            "h1_price_response_n": sum(
                1 for r in crs
                if r["replaced_h1_price_delta"] != r["normal_h1_price_delta"]
            ),
            "terminal_response_n": sum(
                1 for r in crs if r["replacement_terminal_effect"] != 0
            ),
            "terminal_effect": stats([
                float(r["replacement_terminal_effect"]) for r in crs
            ]),
        }

    payload = {
        "schema": "kaggriculture.p12-day3h0-action-replacement.aggregate.v0",
        "case_count": len(rows),
        "action_changed_case_count": len(changed),
        "action_unchanged_case_count": len(unchanged),
        "changed_cases": {
            "h1_inventory_response_count": sum(
                1 for r in changed
                if r["replaced_h1_inventory_delta"] != r["normal_h1_inventory_delta"]
            ),
            "h1_price_response_count": sum(
                1 for r in changed
                if r["replaced_h1_price_delta"] != r["normal_h1_price_delta"]
            ),
            "terminal_response_count": sum(
                1 for r in changed if r["replacement_terminal_effect"] != 0
            ),
            "terminal_effect": stats([
                float(r["replacement_terminal_effect"]) for r in changed
            ]),
        },
        "by_original_terminal_group": by_group,
        "rows": rows,
        "boundary": [
            "Only cases where current and normal-P12 Day3 Hour0 selected-agent actions differ constitute an active replacement.",
            "No response in an unchanged-action case is not evidence about causality.",
            "A response can show sensitivity to the transplanted action but does not identify which action field mattered.",
            "Opponent action and resolver processing remain outside this intervention.",
        ],
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "case_count": payload["case_count"],
        "action_changed_case_count": payload["action_changed_case_count"],
        "changed_cases": payload["changed_cases"],
        "by_original_terminal_group": payload["by_original_terminal_group"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
