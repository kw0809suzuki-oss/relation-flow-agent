#!/usr/bin/env python3
"""MILK Market Raw History Presence Probe fresh10 v0.

Question:
When A/B have the same current MILK market snapshot at the last compact-MILK-
equal decision point, did their immediately preceding live MILK market history
already differ?

This probe does NOT test whether history predicts Cash or terminal value.
It only tests whether a raw historical difference exists before the decision.

Fixed test condition:
- previous 6 completed turns
- raw MILK price and market inventory only
- no trend, slope, moving average, score, or fitted feature
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_milk_physical_precursor_audit_fresh10_v0 as phys

CASES = horizon.CASES
WINDOW_TURNS = 6
OUT = Path("milk_market_raw_history_presence_probe_fresh10_v0_result.json")


def tp(t: str) -> Tuple[int, int]:
    return tuple(map(int, t[1:].replace("h", " ").split()))


def previous_common_turns(
    a_rows: Dict[str, Any],
    b_rows: Dict[str, Any],
    decision_t: str,
    n: int,
) -> List[str]:
    d = tp(decision_t)
    turns = sorted(
        [
            t for t in set(a_rows) & set(b_rows)
            if tp(t) < d
        ],
        key=tp,
    )
    return turns[-n:]


def raw_series(arm: Dict[str, Any], turns: List[str]) -> List[Dict[str, Any]]:
    out = []
    for t in turns:
        row = arm["pre_market"][t]
        out.append({
            "timestamp": t,
            "price": float(row["market_price_milk"]),
            "inventory": int(row["market_inventory_milk"]),
        })
    return out


def first_difference(
    a_series: List[Dict[str, Any]],
    b_series: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    for a, b in zip(a_series, b_series):
        if (
            float(a["price"]) != float(b["price"])
            or int(a["inventory"]) != int(b["inventory"])
        ):
            return {
                "timestamp": a["timestamp"],
                "A": a,
                "B": b,
                "price_delta_B_minus_A": float(b["price"]) - float(a["price"]),
                "inventory_delta_B_minus_A": int(b["inventory"]) - int(a["inventory"]),
            }
    return None


def decision_point(a: Dict[str, Any], b: Dict[str, Any]):
    sell_diff = phys.first_realized_sell_difference(a, b)
    if sell_diff is None:
        return None, "NO_REALIZED_MILK_SELL_DIFFERENCE"

    precursor = phys.physical_difference_trace(a, b, sell_diff["timestamp"])
    first = precursor.get("first_physical_difference")
    if not first or not first.get("last_equal_timestamp"):
        return None, "NO_COMPACT_PHYSICAL_PRECURSOR"

    return first["last_equal_timestamp"], "OBSERVED"


def main():
    cases = []

    for seed, seat in CASES:
        a = phys.play(seed, seat, "A")
        b = phys.play(seed, seat, "B")

        decision_t, status = decision_point(a, b)
        delta_self = b["terminal"]["self"] - a["terminal"]["self"]

        if status != "OBSERVED":
            cases.append({
                "seed": seed,
                "seat": seat,
                "delta_terminal_self_B_minus_A": delta_self,
                "status": status,
            })
            continue

        ar = a["pre_market"][decision_t]
        br = b["pre_market"][decision_t]

        current_a = {
            "price": float(ar["market_price_milk"]),
            "inventory": int(ar["market_inventory_milk"]),
        }
        current_b = {
            "price": float(br["market_price_milk"]),
            "inventory": int(br["market_inventory_milk"]),
        }
        current_equal = current_a == current_b

        turns = previous_common_turns(
            a["pre_market"],
            b["pre_market"],
            decision_t,
            WINDOW_TURNS,
        )
        a_series = raw_series(a, turns)
        b_series = raw_series(b, turns)
        fd = first_difference(a_series, b_series)

        cases.append({
            "seed": seed,
            "seat": seat,
            "delta_terminal_self_B_minus_A": delta_self,
            "status": "OBSERVED",
            "decision_timestamp": decision_t,
            "current_snapshot": {
                "A": current_a,
                "B": current_b,
                "exact_equal": current_equal,
            },
            "history_window": {
                "requested_previous_turns": WINDOW_TURNS,
                "observed_previous_turns": len(turns),
                "timestamps": turns,
                "A_raw": a_series,
                "B_raw": b_series,
                "raw_history_exact_equal": a_series == b_series,
                "first_raw_difference": fd,
            },
        })

    observed = [c for c in cases if c.get("status") == "OBSERVED"]
    equal_current = [
        c for c in observed
        if c["current_snapshot"]["exact_equal"]
    ]
    diff_current = [
        c for c in observed
        if not c["current_snapshot"]["exact_equal"]
    ]

    result = {
        "schema": "kaggriculture.milk-market-raw-history-presence-probe.fresh10.result.v0",
        "window_previous_turns": WINDOW_TURNS,
        "summary": {
            "observed_compact_precursor_cases": len(observed),
            "current_snapshot_exact_equal_cases": len(equal_current),
            "current_snapshot_diff_cases": len(diff_current),
            "equal_current_with_identical_raw_history": sum(
                1 for c in equal_current
                if c["history_window"]["raw_history_exact_equal"]
            ),
            "equal_current_with_different_raw_history": sum(
                1 for c in equal_current
                if not c["history_window"]["raw_history_exact_equal"]
            ),
            "by_seed_equal_current": {
                str(c["seed"]): {
                    "delta_terminal_self_B_minus_A": c[
                        "delta_terminal_self_B_minus_A"
                    ],
                    "decision_timestamp": c["decision_timestamp"],
                    "raw_history_exact_equal": c["history_window"][
                        "raw_history_exact_equal"
                    ],
                    "first_raw_difference": c["history_window"][
                        "first_raw_difference"
                    ],
                }
                for c in equal_current
            },
            "by_seed_current_diff": {
                str(c["seed"]): {
                    "delta_terminal_self_B_minus_A": c[
                        "delta_terminal_self_B_minus_A"
                    ],
                    "decision_timestamp": c["decision_timestamp"],
                    "current_snapshot": c["current_snapshot"],
                }
                for c in diff_current
            },
        },
        "cases": cases,
        "boundary": [
            "This probe asks only whether a raw historical MILK market difference exists before the decision.",
            "It does not test whether history predicts later Cash, terminal self, or whether value should move/hold.",
            "The history window is fixed at the previous 6 completed turns for this probe.",
            "No trend, slope, persistence, moving average, score, or fitted feature is created.",
            "Only cases with exact-equal current MILK price and inventory are used to answer the primary question.",
            "A/B already differ elsewhere in the Battle path; any historical difference is descriptive, not causal.",
        ],
    }

    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "MILK_MARKET_RAW_HISTORY_PRESENCE "
        + json.dumps(
            {
                "summary": result["summary"],
                "cases": [
                    {
                        "seed": c["seed"],
                        "status": c["status"],
                        "decision_timestamp": c.get("decision_timestamp"),
                        "current_snapshot_exact_equal": (
                            c.get("current_snapshot", {}).get("exact_equal")
                        ),
                        "raw_history_exact_equal": (
                            c.get("history_window", {}).get(
                                "raw_history_exact_equal"
                            )
                        ),
                        "first_raw_difference": (
                            c.get("history_window", {}).get(
                                "first_raw_difference"
                            )
                        ),
                    }
                    for c in cases
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
