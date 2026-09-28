#!/usr/bin/env python3
"""Value Transition Timing Audit fresh10 v0.

A = Current D14
B = Seed reopen

For each case with a compact MILK precursor:
1. find the last compact-MILK-equal live state,
2. identify which arm submits more HARVEST actions while standing on a COW
   with visible yield,
3. follow each arm to its next realized SELL MILK boundary,
4. record decision-time World state and later realized MILK Cash.

This is an observational matched-boundary audit. A/B already differ elsewhere
in the Battle path, so "moved first" is NOT treated as an isolated causal
intervention.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_milk_physical_precursor_audit_fresh10_v0 as phys
import run_milk_stage_action_separator_fresh10_v0 as stage

CASES = horizon.CASES
OUT = Path("value_transition_timing_audit_fresh10_v0_result.json")


def tp(t: str) -> Tuple[int, int]:
    return tuple(map(int, t[1:].replace("h", " ").split()))


def after_or_equal(t: str, start: str) -> bool:
    return tp(t) >= tp(start)


def turn_distance(a: str, b: str) -> int:
    da, ha = tp(a)
    db, hb = tp(b)
    return (db - da) * 24 + (hb - ha)


def realized_sell_signature(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "units": len(events),
        "cash": sum(float(e["cash_delta"]) for e in events),
        "prices": [float(e["unit_price"]) for e in events],
        "market_inventory_before": [
            int(e["market_inventory_before"]) for e in events
        ],
    }


def next_sell(arm: Dict[str, Any], start: str) -> Optional[Dict[str, Any]]:
    turns = sorted(
        [
            t for t in arm["realized_milk_sell_by_turn"]
            if after_or_equal(t, start)
        ],
        key=tp,
    )
    if not turns:
        return None
    t = turns[0]
    events = arm["realized_milk_sell_by_turn"][t]
    return {
        "timestamp": t,
        "turns_after_decision": turn_distance(start, t),
        **realized_sell_signature(events),
    }


def realized_after(arm: Dict[str, Any], start: str) -> Dict[str, Any]:
    events = []
    for t, rows in arm["realized_milk_sell_by_turn"].items():
        if after_or_equal(t, start):
            events.extend(rows)
    return {
        "units": len(events),
        "cash": sum(float(e["cash_delta"]) for e in events),
        "avg_realized_price": (
            sum(float(e["cash_delta"]) for e in events) / len(events)
            if events else None
        ),
    }


def first_sell_ready_change(
    arm: Dict[str, Any],
    start: str,
) -> Optional[Dict[str, Any]]:
    rows = arm["pre_market"]
    turns = sorted([t for t in rows if after_or_equal(t, start)], key=tp)
    if not turns:
        return None

    start_ready = int(
        (rows.get(start, {}) or {}).get("state", {}).get("sell_ready_milk", 0) or 0
    )
    previous = start_ready
    for t in turns:
        ready = int(rows[t]["state"].get("sell_ready_milk", 0) or 0)
        if ready != previous:
            return {
                "timestamp": t,
                "turns_after_decision": turn_distance(start, t),
                "previous_sell_ready": previous,
                "sell_ready": ready,
                "direction": "UP" if ready > previous else "DOWN",
            }
        previous = ready
    return None


def decision_world(arm: Dict[str, Any], t: str) -> Dict[str, Any]:
    pre_unit = arm["pre_unit"][t]
    pre_market = arm["pre_market"][t]
    return {
        "milk_state_pre_unit": phys.compact_physical(pre_unit["state"]),
        "milk_state_pre_market": phys.compact_physical(pre_market["state"]),
        "market_price_milk": pre_market["market_price_milk"],
        "market_inventory_milk": pre_market["market_inventory_milk"],
        "sell_milk_request": pre_unit["sell_milk_request"],
        "all_market_orders": pre_unit["all_market_orders"],
        "unit_actions": pre_unit["unit_actions"],
        "harvestable_cow_harvest": stage.harvestable_requests(
            pre_unit["unit_actions"]
        ),
    }


def arm_name_from_harvest_counts(a_count: int, b_count: int) -> Optional[str]:
    if a_count > b_count:
        return "A"
    if b_count > a_count:
        return "B"
    return None


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
        if not first or not first.get("last_equal_timestamp"):
            cases.append({
                "seed": seed,
                "seat": seat,
                "group": group,
                "delta_self": delta_self,
                "status": "NO_COMPACT_PHYSICAL_PRECURSOR",
                "sell_boundary": sell_diff["timestamp"],
            })
            continue

        t = first["last_equal_timestamp"]
        aw = decision_world(a, t)
        bw = decision_world(b, t)

        a_h = len(aw["harvestable_cow_harvest"])
        b_h = len(bw["harvestable_cow_harvest"])
        mover = arm_name_from_harvest_counts(a_h, b_h)

        arm_map = {"A": a, "B": b}
        term_map = {
            "A": a["terminal"]["self"],
            "B": b["terminal"]["self"],
        }

        if mover is None:
            cases.append({
                "seed": seed,
                "seat": seat,
                "group": group,
                "delta_self": delta_self,
                "status": "NO_UNIQUE_EARLY_MOVER",
                "decision_timestamp": t,
                "A_harvestable_cow_harvest_count": a_h,
                "B_harvestable_cow_harvest_count": b_h,
            })
            continue

        other = "B" if mover == "A" else "A"
        mover_arm = arm_map[mover]
        other_arm = arm_map[other]

        mover_next_sell = next_sell(mover_arm, t)
        other_next_sell = next_sell(other_arm, t)
        mover_after = realized_after(mover_arm, t)
        other_after = realized_after(other_arm, t)

        mover_world = aw if mover == "A" else bw
        other_world = bw if mover == "A" else aw

        cases.append({
            "seed": seed,
            "seat": seat,
            "group": group,
            "delta_self": delta_self,
            "status": "OBSERVED",
            "decision_timestamp": t,
            "first_milk_physical_difference": first["timestamp"],
            "first_milk_sell_difference": sell_diff["timestamp"],
            "early_mover": mover,
            "later_arm": other,
            "decision_world": {
                "A": aw,
                "B": bw,
                "mover_minus_other": {
                    "market_price_milk": (
                        float(mover_world["market_price_milk"])
                        - float(other_world["market_price_milk"])
                    ),
                    "market_inventory_milk": (
                        int(mover_world["market_inventory_milk"])
                        - int(other_world["market_inventory_milk"])
                    ),
                },
            },
            "next_sell": {
                "mover": mover_next_sell,
                "other": other_next_sell,
            },
            "post_decision_realized_milk": {
                "mover": mover_after,
                "other": other_after,
                "mover_minus_other_cash": (
                    mover_after["cash"] - other_after["cash"]
                ),
                "mover_minus_other_units": (
                    mover_after["units"] - other_after["units"]
                ),
            },
            "sell_ready_transition": {
                "mover": first_sell_ready_change(mover_arm, t),
                "other": first_sell_ready_change(other_arm, t),
            },
            "terminal": {
                "mover_self": term_map[mover],
                "other_self": term_map[other],
                "mover_minus_other_self": term_map[mover] - term_map[other],
            },
        })

    observed = [c for c in cases if c.get("status") == "OBSERVED"]

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    summary = {
        "observed_cases": len(observed),
        "mover_is_B": sum(1 for c in observed if c["early_mover"] == "B"),
        "mover_is_A": sum(1 for c in observed if c["early_mover"] == "A"),
        "mover_terminal_better": sum(
            1 for c in observed if c["terminal"]["mover_minus_other_self"] > 0
        ),
        "mover_terminal_worse": sum(
            1 for c in observed if c["terminal"]["mover_minus_other_self"] < 0
        ),
        "mover_milk_cash_better": sum(
            1
            for c in observed
            if c["post_decision_realized_milk"]["mover_minus_other_cash"] > 0
        ),
        "mover_milk_cash_worse": sum(
            1
            for c in observed
            if c["post_decision_realized_milk"]["mover_minus_other_cash"] < 0
        ),
        "mean_mover_minus_other_terminal_self": mean([
            c["terminal"]["mover_minus_other_self"] for c in observed
        ]),
        "mean_mover_minus_other_milk_cash": mean([
            c["post_decision_realized_milk"]["mover_minus_other_cash"]
            for c in observed
        ]),
        "mean_decision_market_price_diff": mean([
            c["decision_world"]["mover_minus_other"]["market_price_milk"]
            for c in observed
        ]),
        "mean_decision_market_inventory_diff": mean([
            c["decision_world"]["mover_minus_other"]["market_inventory_milk"]
            for c in observed
        ]),
        "by_group": {},
    }

    for group in ("SELF_IMPROVED", "SELF_WORSE"):
        rows = [c for c in observed if c["group"] == group]
        summary["by_group"][group] = {
            "count": len(rows),
            "mover_is_B": sum(1 for c in rows if c["early_mover"] == "B"),
            "mover_is_A": sum(1 for c in rows if c["early_mover"] == "A"),
            "mover_terminal_better": sum(
                1 for c in rows if c["terminal"]["mover_minus_other_self"] > 0
            ),
            "mover_terminal_worse": sum(
                1 for c in rows if c["terminal"]["mover_minus_other_self"] < 0
            ),
            "mover_milk_cash_better": sum(
                1
                for c in rows
                if c["post_decision_realized_milk"]["mover_minus_other_cash"] > 0
            ),
            "mover_milk_cash_worse": sum(
                1
                for c in rows
                if c["post_decision_realized_milk"]["mover_minus_other_cash"] < 0
            ),
            "mean_mover_minus_other_milk_cash": mean([
                c["post_decision_realized_milk"]["mover_minus_other_cash"]
                for c in rows
            ]),
            "mean_decision_market_price_diff": mean([
                c["decision_world"]["mover_minus_other"]["market_price_milk"]
                for c in rows
            ]),
            "by_seed": {
                str(c["seed"]): {
                    "early_mover": c["early_mover"],
                    "delta_self_B_minus_A": c["delta_self"],
                    "mover_minus_other_terminal_self": c["terminal"][
                        "mover_minus_other_self"
                    ],
                    "mover_minus_other_milk_cash": c[
                        "post_decision_realized_milk"
                    ]["mover_minus_other_cash"],
                    "decision_market_price_diff": c["decision_world"][
                        "mover_minus_other"
                    ]["market_price_milk"],
                    "decision_market_inventory_diff": c["decision_world"][
                        "mover_minus_other"
                    ]["market_inventory_milk"],
                    "mover_next_sell": c["next_sell"]["mover"],
                    "other_next_sell": c["next_sell"]["other"],
                }
                for c in rows
            },
        }

    result = {
        "schema": "kaggriculture.value-transition-timing-audit.fresh10.result.v0",
        "summary": summary,
        "cases": cases,
        "boundary": [
            "Comparison begins at the last compact-MILK-equal state before the first compact MILK physical divergence.",
            "Early mover is defined only by more submitted HARVEST actions while standing on visible-yield COWs at that turn.",
            "A/B already differ elsewhere in the Battle path; early movement is not an isolated causal intervention.",
            "Decision-time market state is observed, not held equal.",
            "Post-decision realized MILK Cash is an outcome of the whole subsequent path, not attribution to the one HARVEST choice.",
            "Improved/worse grouping is retrospective.",
        ],
    }

    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "VALUE_TRANSITION_TIMING_AUDIT "
        + json.dumps(
            {
                "summary": summary,
                "cases": [
                    {
                        "seed": c["seed"],
                        "group": c["group"],
                        "status": c["status"],
                        "early_mover": c.get("early_mover"),
                        "delta_self_B_minus_A": c["delta_self"],
                        "mover_minus_other_terminal_self": (
                            c.get("terminal", {}).get("mover_minus_other_self")
                        ),
                        "mover_minus_other_milk_cash": (
                            c.get("post_decision_realized_milk", {}).get(
                                "mover_minus_other_cash"
                            )
                        ),
                        "decision_market_price_diff": (
                            c.get("decision_world", {})
                            .get("mover_minus_other", {})
                            .get("market_price_milk")
                        ),
                        "mover_next_sell": (
                            c.get("next_sell", {}).get("mover")
                        ),
                        "other_next_sell": (
                            c.get("next_sell", {}).get("other")
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
