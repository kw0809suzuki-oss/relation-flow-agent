#!/usr/bin/env python3
"""MILK Market Forward Divergence Probe fresh10 v0.

Primary set:
cases with exact-equal current MILK market snapshot and exact-equal previous
6-turn raw MILK market history at the last compact-MILK-equal decision point.

Question:
Before the first realized SELL MILK boundary difference, does the MILK market
itself (price or inventory) diverge between A and B?

Only MILK market state is examined here. Other-product market differences are
deliberately excluded.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_post_decision_world_first_difference_probe_fresh10_v0 as worldprobe

OUT = Path("milk_market_forward_divergence_probe_fresh10_v0_result.json")
CASES = horizon.CASES


def tp(t: str) -> Tuple[int, int]:
    return tuple(map(int, t[1:].replace("h", " ").split()))


def milk_snapshot(row: Dict[str, Any], phase: str) -> Dict[str, Any]:
    market = row[phase]["public_market"]
    return {
        "price": float(market["prices"]["MILK"]),
        "inventory": int(market["inventory"]["MILK"]),
    }


def milk_events(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        e for e in row.get("market_events", [])
        if e.get("item") == "MILK"
    ]


def main():
    cases = []

    for seed, seat in CASES:
        a = worldprobe.play(seed, seat, "A")
        b = worldprobe.play(seed, seat, "B")

        sell_t = worldprobe.first_realized_milk_sell_difference(a, b)
        if sell_t is None:
            cases.append({"seed": seed, "status": "NO_MILK_SELL_DIFFERENCE"})
            continue

        pd = worldprobe.physical_decision(a, b, sell_t)
        if not pd or not pd["last_equal"]:
            cases.append({
                "seed": seed,
                "status": "NO_COMPACT_PHYSICAL_PRECURSOR",
                "first_milk_sell_difference": sell_t,
            })
            continue

        match = worldprobe.current_and_history_match(a, b, pd["last_equal"])
        if not (match["current_equal"] and match["history_equal"]):
            cases.append({
                "seed": seed,
                "status": "NOT_MATCHED_CURRENT_AND_HISTORY",
                "decision_timestamp": pd["last_equal"],
                "first_milk_sell_difference": sell_t,
            })
            continue

        decision_t = pd["last_equal"]
        turns = sorted(
            [
                t for t in set(a["rows"]) & set(b["rows"])
                if tp(t) >= tp(decision_t) and tp(t) <= tp(sell_t)
            ],
            key=tp,
        )

        first_pre = None
        first_post = None
        first_event_diff = None

        timeline = []
        for t in turns:
            apre = milk_snapshot(a["rows"][t], "pre_market")
            bpre = milk_snapshot(b["rows"][t], "pre_market")
            apost = milk_snapshot(a["rows"][t], "post_market")
            bpost = milk_snapshot(b["rows"][t], "post_market")
            ae = milk_events(a["rows"][t])
            be = milk_events(b["rows"][t])

            timeline.append({
                "timestamp": t,
                "A_pre": apre,
                "B_pre": bpre,
                "pre_equal": apre == bpre,
                "A_milk_events": ae,
                "B_milk_events": be,
                "milk_events_equal": ae == be,
                "A_post": apost,
                "B_post": bpost,
                "post_equal": apost == bpost,
            })

            if first_pre is None and apre != bpre:
                first_pre = {
                    "timestamp": t,
                    "A": apre,
                    "B": bpre,
                }
            if first_event_diff is None and ae != be:
                first_event_diff = {
                    "timestamp": t,
                    "A": ae,
                    "B": be,
                }
            if first_post is None and apost != bpost:
                first_post = {
                    "timestamp": t,
                    "A": apost,
                    "B": bpost,
                }

        sell_pair = tp(sell_t)

        def relation(x):
            if x is None:
                return "NONE_THROUGH_FIRST_SELL_DIFFERENCE"
            p = tp(x["timestamp"])
            if p < sell_pair:
                return "BEFORE_FIRST_SELL_DIFFERENCE"
            if p == sell_pair:
                return "AT_FIRST_SELL_DIFFERENCE"
            return "AFTER_FIRST_SELL_DIFFERENCE"

        cases.append({
            "seed": seed,
            "seat": seat,
            "status": "OBSERVED",
            "delta_terminal_self_B_minus_A": (
                b["terminal"]["self"] - a["terminal"]["self"]
            ),
            "decision_timestamp": decision_t,
            "first_physical_difference": pd["first_physical_difference"],
            "first_milk_sell_difference": sell_t,
            "first_milk_market_pre_difference": first_pre,
            "first_milk_market_pre_relation": relation(first_pre),
            "first_milk_market_event_difference": first_event_diff,
            "first_milk_market_event_relation": relation(first_event_diff),
            "first_milk_market_post_difference": first_post,
            "first_milk_market_post_relation": relation(first_post),
            "timeline": timeline,
        })

    observed = [c for c in cases if c.get("status") == "OBSERVED"]

    def count(field, value):
        return sum(1 for c in observed if c[field] == value)

    result = {
        "schema": "kaggriculture.milk-market-forward-divergence.fresh10.result.v0",
        "summary": {
            "matched_current_and_history_cases": len(observed),
            "pre_market_diverges_before_first_sell": count(
                "first_milk_market_pre_relation",
                "BEFORE_FIRST_SELL_DIFFERENCE",
            ),
            "pre_market_first_diverges_at_first_sell": count(
                "first_milk_market_pre_relation",
                "AT_FIRST_SELL_DIFFERENCE",
            ),
            "pre_market_no_divergence_through_first_sell": count(
                "first_milk_market_pre_relation",
                "NONE_THROUGH_FIRST_SELL_DIFFERENCE",
            ),
            "milk_event_diff_before_first_sell": count(
                "first_milk_market_event_relation",
                "BEFORE_FIRST_SELL_DIFFERENCE",
            ),
            "milk_event_diff_at_first_sell": count(
                "first_milk_market_event_relation",
                "AT_FIRST_SELL_DIFFERENCE",
            ),
            "milk_event_no_diff_through_first_sell": count(
                "first_milk_market_event_relation",
                "NONE_THROUGH_FIRST_SELL_DIFFERENCE",
            ),
            "post_market_diverges_before_first_sell": count(
                "first_milk_market_post_relation",
                "BEFORE_FIRST_SELL_DIFFERENCE",
            ),
            "post_market_first_diverges_at_first_sell": count(
                "first_milk_market_post_relation",
                "AT_FIRST_SELL_DIFFERENCE",
            ),
            "post_market_no_divergence_through_first_sell": count(
                "first_milk_market_post_relation",
                "NONE_THROUGH_FIRST_SELL_DIFFERENCE",
            ),
            "by_seed": {
                str(c["seed"]): {
                    "delta_terminal_self_B_minus_A": c[
                        "delta_terminal_self_B_minus_A"
                    ],
                    "decision_timestamp": c["decision_timestamp"],
                    "first_physical_difference": c["first_physical_difference"],
                    "first_milk_sell_difference": c["first_milk_sell_difference"],
                    "pre_relation": c["first_milk_market_pre_relation"],
                    "event_relation": c["first_milk_market_event_relation"],
                    "post_relation": c["first_milk_market_post_relation"],
                    "first_pre": c["first_milk_market_pre_difference"],
                    "first_event": c["first_milk_market_event_difference"],
                    "first_post": c["first_milk_market_post_difference"],
                }
                for c in observed
            },
        },
        "cases": cases,
        "boundary": [
            "Primary set requires exact-equal current MILK price/inventory and exact-equal previous-6-turn raw MILK price/inventory history.",
            "Only MILK market price, MILK market inventory, and successful MILK market events are compared.",
            "Other-product market divergence is deliberately excluded.",
            "A pre-market MILK difference before the first SELL boundary would show that the MILK market diverged before the return event.",
            "A first difference only at the SELL boundary means the tested MILK market path remained equal until that boundary.",
            "Chronology does not establish causal value of the earlier stage transition.",
        ],
    }

    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "MILK_MARKET_FORWARD_DIVERGENCE "
        + json.dumps(
            {"summary": result["summary"]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
