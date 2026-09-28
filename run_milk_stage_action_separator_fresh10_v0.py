#!/usr/bin/env python3
"""MILK Stage Action Separator fresh10 v0.

Uses the same A/B Seed-reopen battles as MILK Physical Precursor Audit.

For each case with a first physical MILK difference, inspect the self unit
actions submitted at the immediately preceding compact-MILK-equal timestamp.

Question:
Did the stage displacement begin with a different successful-looking HARVEST
choice on a COW that already had MILK output?

Observation only.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_milk_physical_precursor_audit_fresh10_v0 as phys

OUT = Path("milk_stage_action_separator_fresh10_v0_result.json")
CASES = horizon.CASES


def op_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    c = Counter()
    for r in rows:
        action = r.get("action") or ["PASS"]
        op = action[0] if action else "PASS"
        c[str(op)] += 1
    return dict(sorted(c.items()))


def harvestable_requests(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        action = r.get("action") or ["PASS"]
        if not action or action[0] != "HARVEST":
            continue
        y = r.get("standing_cow_yield_before")
        if y is None or int(y) <= 0:
            continue
        out.append({
            "actor": r.get("actor"),
            "actor_index": r.get("actor_index"),
            "position": r.get("position"),
            "action": action,
            "milk_carried_before": r.get("milk_carried_before"),
            "standing_cow_yield_before": y,
        })
    return out


def milk_drop_requests(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        action = r.get("action") or ["PASS"]
        if not action or action[0] not in ("DROP", "PLACE"):
            continue
        if int(r.get("milk_carried_before", 0) or 0) <= 0:
            continue
        out.append({
            "actor": r.get("actor"),
            "actor_index": r.get("actor_index"),
            "position": r.get("position"),
            "action": action,
            "milk_carried_before": r.get("milk_carried_before"),
        })
    return out


def action_signature(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "actor": r.get("actor"),
            "position": r.get("position"),
            "action": r.get("action"),
            "milk_carried_before": r.get("milk_carried_before"),
            "standing_cow_yield_before": r.get("standing_cow_yield_before"),
        }
        for r in rows
    ]


def classify(a_rows: List[Dict[str, Any]], b_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ah = harvestable_requests(a_rows)
    bh = harvestable_requests(b_rows)
    ad = milk_drop_requests(a_rows)
    bd = milk_drop_requests(b_rows)

    if len(ah) > len(bh):
        label = "A_MORE_HARVESTABLE_COW_HARVEST"
    elif len(bh) > len(ah):
        label = "B_MORE_HARVESTABLE_COW_HARVEST"
    elif len(ah) == len(bh) and len(ah) > 0 and ah != bh:
        label = "HARVEST_TARGET_OR_ACTOR_DIFFERS"
    elif len(ad) != len(bd):
        label = "MILK_DROP_STAGE_ACTION_DIFFERS"
    elif action_signature(a_rows) != action_signature(b_rows):
        label = "OTHER_UNIT_ACTION_DIFFERS"
    else:
        label = "NO_SELF_UNIT_ACTION_SEPARATOR"

    return {
        "label": label,
        "A_harvestable_cow_harvest": ah,
        "B_harvestable_cow_harvest": bh,
        "A_milk_drop_requests": ad,
        "B_milk_drop_requests": bd,
        "A_op_counts": op_counts(a_rows),
        "B_op_counts": op_counts(b_rows),
    }


def main():
    cases = []

    for seed, seat in CASES:
        a = phys.play(seed, seat, "A")
        b = phys.play(seed, seat, "B")
        delta_self = b["terminal"]["self"] - a["terminal"]["self"]
        group = (
            "SELF_IMPROVED" if delta_self > 0
            else "SELF_WORSE" if delta_self < 0
            else "SELF_EQUAL"
        )

        sell_diff = phys.first_realized_sell_difference(a, b)
        if sell_diff is None:
            cases.append({
                "seed": seed,
                "seat": seat,
                "group": group,
                "delta_self": delta_self,
                "status": "NO_REALIZED_MILK_SELL_DIFFERENCE",
            })
            continue

        precursor = phys.physical_difference_trace(a, b, sell_diff["timestamp"])
        first = precursor.get("first_physical_difference")
        if not first:
            cases.append({
                "seed": seed,
                "seat": seat,
                "group": group,
                "delta_self": delta_self,
                "sell_boundary": sell_diff["timestamp"],
                "status": "NO_COMPACT_PHYSICAL_PRECURSOR",
            })
            continue

        last_equal = first.get("last_equal_timestamp")
        if not last_equal:
            cases.append({
                "seed": seed,
                "seat": seat,
                "group": group,
                "delta_self": delta_self,
                "sell_boundary": sell_diff["timestamp"],
                "first_physical_difference": first["timestamp"],
                "status": "NO_LAST_EQUAL_TIMESTAMP",
            })
            continue

        a_row = a["pre_unit"].get(last_equal)
        b_row = b["pre_unit"].get(last_equal)
        if not a_row or not b_row:
            raise RuntimeError(f"missing pre_unit row {seed} {last_equal}")

        cls = classify(a_row["unit_actions"], b_row["unit_actions"])

        cases.append({
            "seed": seed,
            "seat": seat,
            "group": group,
            "delta_self": delta_self,
            "status": "OBSERVED",
            "last_equal_timestamp": last_equal,
            "first_physical_difference": first["timestamp"],
            "sell_boundary": sell_diff["timestamp"],
            "A_last_equal_state": phys.compact_physical(a_row["state"]),
            "B_last_equal_state": phys.compact_physical(b_row["state"]),
            "A_action_signature": action_signature(a_row["unit_actions"]),
            "B_action_signature": action_signature(b_row["unit_actions"]),
            "classification": cls,
            "next_physical_state": {
                "A": first["A"],
                "B": first["B"],
            },
        })

    groups = {}
    for group in ("SELF_IMPROVED", "SELF_WORSE"):
        rows = [c for c in cases if c["group"] == group]
        labels = Counter(
            c["classification"]["label"]
            for c in rows
            if c.get("classification")
        )
        groups[group] = {
            "count": len(rows),
            "observed_action_separator_cases": sum(
                1 for c in rows if c.get("status") == "OBSERVED"
            ),
            "classification_counts": dict(sorted(labels.items())),
            "by_seed": {
                str(c["seed"]): {
                    "delta_self": c["delta_self"],
                    "status": c["status"],
                    "last_equal_timestamp": c.get("last_equal_timestamp"),
                    "first_physical_difference": c.get("first_physical_difference"),
                    "sell_boundary": c.get("sell_boundary"),
                    "classification": (
                        c["classification"]["label"]
                        if c.get("classification")
                        else None
                    ),
                    "A_op_counts": (
                        c["classification"]["A_op_counts"]
                        if c.get("classification")
                        else None
                    ),
                    "B_op_counts": (
                        c["classification"]["B_op_counts"]
                        if c.get("classification")
                        else None
                    ),
                }
                for c in rows
            },
        }

    result = {
        "schema": "kaggriculture.milk-stage-action-separator.fresh10.result.v0",
        "group_summary": groups,
        "cases": cases,
        "boundary": [
            "The inspected action is submitted at the last compact-MILK-equal timestamp immediately before the first compact MILK physical difference.",
            "A HARVEST is called harvestable-COW HARVEST only when the actor is already standing on a COW with yield_units > 0 in the live pre-action state.",
            "This identifies the direct action/state transition associated with the first MILK stage displacement; it does not explain why the agent chose that action.",
            "A/B differ only in D14 BUY_SEED suppression.",
            "Improved/worse grouping is retrospective.",
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MILK_STAGE_ACTION_SEPARATOR " + json.dumps({
        "group_summary": groups,
        "cases": [
            {
                "seed": c["seed"],
                "group": c["group"],
                "delta_self": c["delta_self"],
                "status": c["status"],
                "last_equal": c.get("last_equal_timestamp"),
                "first_physical_difference": c.get("first_physical_difference"),
                "classification": (
                    c["classification"]["label"]
                    if c.get("classification")
                    else None
                ),
            }
            for c in cases
        ],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
