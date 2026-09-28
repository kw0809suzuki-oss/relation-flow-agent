#!/usr/bin/env python3
"""MILK Return Path Boundary Audit fresh10 v0.

Primary set:
A/B cases whose MILK current market snapshot and previous 6-turn raw MILK
market history are exactly equal at the last compact-MILK-equal decision point.

Starting from the already-known first compact physical MILK divergence, record
the first downstream MILK-specific Return-path differences:

- milk-carrying DROP action
- SELL-ready MILK in shed after unit actions / before market
- submitted SELL MILK request
- successfully executed SELL MILK

No preference ordering is assumed. The audit reports timestamps and then names
the chronologically earliest downstream boundary difference(s).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_milk_physical_precursor_audit_fresh10_v0 as phys
import run_post_decision_world_first_difference_probe_fresh10_v0 as worldprobe

OUT = Path("milk_return_path_boundary_audit_fresh10_v0_result.json")
CASES = horizon.CASES


def tp(t: str) -> Tuple[int, int]:
    return tuple(map(int, t[1:].replace("h", " ").split()))


def distance(a: str, b: str) -> int:
    da, ha = tp(a)
    db, hb = tp(b)
    return (db - da) * 24 + (hb - ha)


def milk_drop_signature(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for r in row.get("unit_actions", []) or []:
        action = r.get("action") or ["PASS"]
        if not isinstance(action, list) or not action:
            continue
        if action[0] != "DROP":
            continue
        milk = int(r.get("milk_carried_before", 0) or 0)
        if milk <= 0:
            continue
        out.append({
            "actor": r.get("actor"),
            "actor_index": r.get("actor_index"),
            "position": r.get("position"),
            "milk_carried_before": milk,
            "action": list(action),
        })
    return out


def sell_request_signature(row: Dict[str, Any]) -> List[Any]:
    return json.loads(json.dumps(row.get("sell_milk_request", []) or []))


def sell_execution_signature(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "cash_delta": float(e["cash_delta"]),
            "unit_price": float(e["unit_price"]),
            "market_inventory_before": int(e["market_inventory_before"]),
            "item_stock_before": (
                None if e.get("item_stock_before") is None
                else int(e["item_stock_before"])
            ),
            "item_stock_after": (
                None if e.get("item_stock_after") is None
                else int(e["item_stock_after"])
            ),
        }
        for e in events
    ]


def first_difference(
    turns: List[str],
    a_fn,
    b_fn,
) -> Optional[Dict[str, Any]]:
    for t in turns:
        av = a_fn(t)
        bv = b_fn(t)
        if av != bv:
            return {
                "timestamp": t,
                "A": av,
                "B": bv,
            }
    return None


def boundary_order(boundaries: Dict[str, Optional[Dict[str, Any]]]):
    present = [
        (name, rec)
        for name, rec in boundaries.items()
        if rec is not None
    ]
    if not present:
        return {
            "earliest_timestamp": None,
            "earliest_boundaries": [],
        }
    earliest_pair = min(tp(rec["timestamp"]) for _, rec in present)
    earliest_names = [
        name for name, rec in present
        if tp(rec["timestamp"]) == earliest_pair
    ]
    earliest_t = next(
        rec["timestamp"] for _, rec in present
        if tp(rec["timestamp"]) == earliest_pair
    )
    return {
        "earliest_timestamp": earliest_t,
        "earliest_boundaries": sorted(earliest_names),
    }


def main():
    cases = []

    for seed, seat in CASES:
        a = phys.play(seed, seat, "A")
        b = phys.play(seed, seat, "B")

        delta_self = b["terminal"]["self"] - a["terminal"]["self"]
        sell_diff = phys.first_realized_sell_difference(a, b)
        if sell_diff is None:
            cases.append({
                "seed": seed,
                "status": "NO_REALIZED_MILK_SELL_DIFFERENCE",
                "delta_terminal_self_B_minus_A": delta_self,
            })
            continue

        precursor = phys.physical_difference_trace(a, b, sell_diff["timestamp"])
        first = precursor.get("first_physical_difference")
        if not first or not first.get("last_equal_timestamp"):
            cases.append({
                "seed": seed,
                "status": "NO_COMPACT_PHYSICAL_PRECURSOR",
                "delta_terminal_self_B_minus_A": delta_self,
                "first_milk_sell_difference": sell_diff["timestamp"],
            })
            continue

        decision_t = first["last_equal_timestamp"]
        first_physical_t = first["timestamp"]

        # Reuse the exact same matched-current/history criterion from the
        # previous forward-World probes.
        # phys.play pre_market rows expose MILK price/inventory directly.
        current_a = {
            "price": float(a["pre_market"][decision_t]["market_price_milk"]),
            "inventory": int(a["pre_market"][decision_t]["market_inventory_milk"]),
        }
        current_b = {
            "price": float(b["pre_market"][decision_t]["market_price_milk"]),
            "inventory": int(b["pre_market"][decision_t]["market_inventory_milk"]),
        }

        common_prior = sorted(
            [
                t for t in set(a["pre_market"]) & set(b["pre_market"])
                if tp(t) < tp(decision_t)
            ],
            key=tp,
        )[-6:]

        hist_a = [
            {
                "timestamp": t,
                "price": float(a["pre_market"][t]["market_price_milk"]),
                "inventory": int(a["pre_market"][t]["market_inventory_milk"]),
            }
            for t in common_prior
        ]
        hist_b = [
            {
                "timestamp": t,
                "price": float(b["pre_market"][t]["market_price_milk"]),
                "inventory": int(b["pre_market"][t]["market_inventory_milk"]),
            }
            for t in common_prior
        ]

        if not (current_a == current_b and hist_a == hist_b):
            cases.append({
                "seed": seed,
                "status": "NOT_MATCHED_CURRENT_AND_HISTORY",
                "delta_terminal_self_B_minus_A": delta_self,
                "decision_timestamp": decision_t,
                "first_physical_difference": first_physical_t,
                "first_milk_sell_difference": sell_diff["timestamp"],
            })
            continue

        end_t = sell_diff["timestamp"]
        turns = sorted(
            [
                t for t in set(a["pre_unit"]) & set(b["pre_unit"])
                if tp(t) >= tp(first_physical_t) and tp(t) <= tp(end_t)
            ],
            key=tp,
        )

        drop_diff = first_difference(
            turns,
            lambda t: milk_drop_signature(a["pre_unit"][t]),
            lambda t: milk_drop_signature(b["pre_unit"][t]),
        )

        ready_diff = first_difference(
            turns,
            lambda t: int(a["pre_market"][t]["state"]["sell_ready_milk"]),
            lambda t: int(b["pre_market"][t]["state"]["sell_ready_milk"]),
        )

        request_diff = first_difference(
            turns,
            lambda t: sell_request_signature(a["pre_unit"][t]),
            lambda t: sell_request_signature(b["pre_unit"][t]),
        )

        execution_diff = first_difference(
            turns,
            lambda t: sell_execution_signature(
                a["realized_milk_sell_by_turn"].get(t, [])
            ),
            lambda t: sell_execution_signature(
                b["realized_milk_sell_by_turn"].get(t, [])
            ),
        )

        boundaries = {
            "MILK_DROP_ACTION": drop_diff,
            "SELL_READY_SHED": ready_diff,
            "SELL_REQUEST": request_diff,
            "EXECUTED_SELL": execution_diff,
        }
        order = boundary_order(boundaries)

        cases.append({
            "seed": seed,
            "seat": seat,
            "status": "OBSERVED",
            "delta_terminal_self_B_minus_A": delta_self,
            "decision_timestamp": decision_t,
            "first_physical_difference": first_physical_t,
            "first_milk_sell_difference": end_t,
            "boundaries": boundaries,
            "earliest_downstream": {
                **order,
                "turns_after_first_physical_difference": (
                    None
                    if order["earliest_timestamp"] is None
                    else distance(first_physical_t, order["earliest_timestamp"])
                ),
            },
        })

    observed = [c for c in cases if c.get("status") == "OBSERVED"]

    boundary_first_counts = {}
    for c in observed:
        for name in c["earliest_downstream"]["earliest_boundaries"]:
            boundary_first_counts[name] = boundary_first_counts.get(name, 0) + 1

    boundary_presence_counts = {}
    for name in (
        "MILK_DROP_ACTION",
        "SELL_READY_SHED",
        "SELL_REQUEST",
        "EXECUTED_SELL",
    ):
        boundary_presence_counts[name] = sum(
            1 for c in observed if c["boundaries"][name] is not None
        )

    result = {
        "schema": "kaggriculture.milk-return-path-boundary-audit.fresh10.result.v0",
        "summary": {
            "matched_current_and_history_cases": len(observed),
            "earliest_boundary_counts": dict(sorted(boundary_first_counts.items())),
            "boundary_presence_counts": boundary_presence_counts,
            "by_seed": {
                str(c["seed"]): {
                    "delta_terminal_self_B_minus_A": c[
                        "delta_terminal_self_B_minus_A"
                    ],
                    "first_physical_difference": c[
                        "first_physical_difference"
                    ],
                    "first_milk_sell_difference": c[
                        "first_milk_sell_difference"
                    ],
                    "earliest_downstream": c["earliest_downstream"],
                    "boundary_timestamps": {
                        name: (
                            None if rec is None else rec["timestamp"]
                        )
                        for name, rec in c["boundaries"].items()
                    },
                }
                for c in observed
            },
        },
        "cases": cases,
        "boundary": [
            "Primary set requires exact-equal current MILK market snapshot and exact-equal previous-6-turn raw MILK market history.",
            "The already-known first COW/Carry physical MILK divergence is the starting boundary and is not re-ranked.",
            "MILK_DROP_ACTION means a submitted DROP by an actor carrying MILK in the live pre-unit state.",
            "SELL_READY_SHED is measured after unit actions and before market execution, matching the public rule that SELL consumes shed inventory.",
            "SELL_REQUEST is the submitted MILK market order; EXECUTED_SELL is successful public-rule market execution.",
            "Earliest downstream boundary is chronology only and does not imply strategic superiority or causality to terminal result.",
        ],
    }

    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "MILK_RETURN_PATH_BOUNDARY_AUDIT "
        + json.dumps(
            {"summary": result["summary"]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
