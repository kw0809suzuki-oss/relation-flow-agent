#!/usr/bin/env python3
"""Aggregate Battle Value Stock Balance v0 artifacts.

Produces a compact accounting map only. It does not name stock provenance.
"""
import glob
import json
from collections import defaultdict
from pathlib import Path

PRODUCTS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def residual(opp, self_):
    return opp - self_


def event_units(events, player, op, item):
    return sum(
        1 for e in events
        if int(e.get("player", -1)) == player
        and e.get("op") == op
        and e.get("item") == item
    )


def analyze_case(raw):
    seed = int(raw["seed"])
    seat = int(raw["seat"])
    self_p = seat
    opp_p = 1 - seat
    turns = sorted(
        raw["market_turns"],
        key=lambda x: (int(x["day"]), int(x["hour"])),
    )
    if not turns:
        raise ValueError(f"seed {seed}: no market turns")

    start = turns[0]["before"]
    end = turns[-1]["before"]  # Day24 h0 endpoint, before Day24 market.
    interval_turns = [
        t for t in turns
        if int(t["day"]) * 24 + int(t["hour"]) < 24 * 24
    ]

    integrity = {
        "market_turn_count": len(turns),
        "interval_market_turn_count": len(interval_turns),
        "carried_changed_during_market_cells": 0,
        "shed_market_delta_mismatch_cells": 0,
        "stock_balance_mismatch_cells": 0,
    }

    by_player = {0: {}, 1: {}}

    for p in (0, 1):
        for item in PRODUCTS:
            start_shed = int(start[p]["shed_by_item"][item])
            start_carried = int(start[p]["carried_by_item"][item])
            start_on_hand = int(start[p]["on_hand_by_item"][item])
            end_shed = int(end[p]["shed_by_item"][item])
            end_carried = int(end[p]["carried_by_item"][item])
            end_on_hand = int(end[p]["on_hand_by_item"][item])

            market_shed_delta = 0
            market_carried_delta = 0
            market_on_hand_delta = 0

            for t in interval_turns:
                b = t["before"][p]
                a = t["after"][p]
                ds = int(a["shed_by_item"][item]) - int(b["shed_by_item"][item])
                dc = int(a["carried_by_item"][item]) - int(b["carried_by_item"][item])
                do = int(a["on_hand_by_item"][item]) - int(b["on_hand_by_item"][item])
                market_shed_delta += ds
                market_carried_delta += dc
                market_on_hand_delta += do

                if dc != 0:
                    integrity["carried_changed_during_market_cells"] += 1

                expected = (
                    event_units(t.get("sell_events", []), p, "BUY_PRODUCT", item)
                    - event_units(t.get("sell_events", []), p, "SELL", item)
                )
                # turn.sell_events contains SELL only by construction; use raw market_events below
                # for the exact market-product accounting check.

            nonmarket_shed_delta = 0
            nonmarket_carried_delta = 0
            nonmarket_on_hand_delta = 0
            for i in range(len(turns) - 1):
                cur = turns[i]
                nxt = turns[i + 1]
                if int(cur["day"]) * 24 + int(cur["hour"]) >= 24 * 24:
                    break
                a = cur["after"][p]
                b2 = nxt["before"][p]
                nonmarket_shed_delta += (
                    int(b2["shed_by_item"][item]) - int(a["shed_by_item"][item])
                )
                nonmarket_carried_delta += (
                    int(b2["carried_by_item"][item]) - int(a["carried_by_item"][item])
                )
                nonmarket_on_hand_delta += (
                    int(b2["on_hand_by_item"][item]) - int(a["on_hand_by_item"][item])
                )

            sell_units = event_units(raw["sell_events"], p, "SELL", item)
            buy_product_units = event_units(raw["market_events"], p, "BUY_PRODUCT", item)

            # Exact observed market product delta from event log.
            expected_market_delta = buy_product_units - sell_units
            if market_shed_delta != expected_market_delta:
                integrity["shed_market_delta_mismatch_cells"] += 1

            if (
                end_shed != start_shed + market_shed_delta + nonmarket_shed_delta
                or end_carried != start_carried + market_carried_delta + nonmarket_carried_delta
                or end_on_hand != start_on_hand + market_on_hand_delta + nonmarket_on_hand_delta
            ):
                integrity["stock_balance_mismatch_cells"] += 1

            by_player[p][item] = {
                "start_shed": start_shed,
                "start_carried": start_carried,
                "start_on_hand": start_on_hand,
                "sell_units": sell_units,
                "buy_product_units": buy_product_units,
                "market_shed_net_change": market_shed_delta,
                "market_carried_net_change": market_carried_delta,
                "market_on_hand_net_change": market_on_hand_delta,
                "between_market_shed_net_change": nonmarket_shed_delta,
                "between_market_carried_net_change": nonmarket_carried_delta,
                "between_market_on_hand_net_change": nonmarket_on_hand_delta,
                "end_shed": end_shed,
                "end_carried": end_carried,
                "end_on_hand": end_on_hand,
            }

    by_item_residual = {}
    for item in PRODUCTS:
        s = by_player[self_p][item]
        o = by_player[opp_p][item]
        by_item_residual[item] = {
            k: residual(o[k], s[k])
            for k in s
        }

    # Compact time map: keep only points where the residual location changes
    # or a SELL occurs for this item at this turn.
    timeline_changes = {item: [] for item in PRODUCTS}
    prev = {item: None for item in PRODUCTS}
    for t in turns:
        timestamp = {"day": int(t["day"]), "hour": int(t["hour"])}
        for item in PRODUCTS:
            sb = t["before"][self_p]
            ob = t["before"][opp_p]
            state = {
                "shed_residual": int(ob["shed_by_item"][item]) - int(sb["shed_by_item"][item]),
                "carried_residual": int(ob["carried_by_item"][item]) - int(sb["carried_by_item"][item]),
                "on_hand_residual": int(ob["on_hand_by_item"][item]) - int(sb["on_hand_by_item"][item]),
            }
            turn_sell_residual = (
                event_units(t.get("sell_events", []), opp_p, "SELL", item)
                - event_units(t.get("sell_events", []), self_p, "SELL", item)
            )
            if state != prev[item] or turn_sell_residual != 0:
                timeline_changes[item].append({
                    **timestamp,
                    **state,
                    "sell_unit_residual_this_turn": turn_sell_residual,
                })
                prev[item] = state

    return {
        "seed": seed,
        "seat": seat,
        "terminal": raw["terminal"],
        "integrity": integrity,
        "self_by_item": by_player[self_p],
        "opponent_by_item": by_player[opp_p],
        "residual_by_item": by_item_residual,
        "residual_timeline_changes": timeline_changes,
    }


def main():
    paths = [
        Path(p) for p in glob.glob(
            "stock-balance-artifacts/**/battle_value_stock_balance_v0_*.json",
            recursive=True,
        )
    ]
    if not paths:
        paths = [
            Path(p) for p in glob.glob(
                "**/battle_value_stock_balance_v0_*_seat*.json",
                recursive=True,
            )
        ]
    paths = sorted(set(paths))
    if len(paths) != 5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}: {paths}")

    cases = [analyze_case(json.loads(p.read_text(encoding="utf-8"))) for p in paths]

    metrics = list(next(iter(cases[0]["self_by_item"].values())).keys())
    mean_by_item = {}
    for item in PRODUCTS:
        mean_by_item[item] = {}
        for metric in metrics:
            self_vals = [c["self_by_item"][item][metric] for c in cases]
            opp_vals = [c["opponent_by_item"][item][metric] for c in cases]
            res_vals = [c["residual_by_item"][item][metric] for c in cases]
            mean_by_item[item][metric] = {
                "self_absolute_mean": mean(self_vals),
                "opponent_absolute_mean": mean(opp_vals),
                "mean_residual_opponent_minus_self": mean(res_vals),
            }

    terminal_self = [float(c["terminal"]["self"]) for c in cases]
    terminal_opp = [float(c["terminal"]["opponent"]) for c in cases]

    payload = {
        "schema": "kaggriculture.strong-origin-v2.battle-value-stock-balance.result.v0",
        "battle_count": len(cases),
        "window": "Day20 h0 inclusive -> Day24 h0 endpoint; SELL Day24 h0 excluded",
        "terminal_absolute": {
            "mean_self": mean(terminal_self),
            "mean_opponent": mean(terminal_opp),
            "mean_margin": mean([s - o for s, o in zip(terminal_self, terminal_opp)]),
        },
        "integrity": {
            "all_cases_97_market_turns": all(c["integrity"]["market_turn_count"] == 97 for c in cases),
            "all_cases_96_interval_market_turns": all(c["integrity"]["interval_market_turn_count"] == 96 for c in cases),
            "carried_changed_during_market_cells": sum(c["integrity"]["carried_changed_during_market_cells"] for c in cases),
            "shed_market_delta_mismatch_cells": sum(c["integrity"]["shed_market_delta_mismatch_cells"] for c in cases),
            "stock_balance_mismatch_cells": sum(c["integrity"]["stock_balance_mismatch_cells"] for c in cases),
        },
        "mean_by_item": mean_by_item,
        "cases": cases,
        "boundary": [
            "shed, carried and on-hand are location/accounting observations only.",
            "between_market_*_net_change is the net stock change from one market-after snapshot to the next market-before snapshot; it is not gross inflow and does not identify its source.",
            "No between-market net change is labeled harvest, DROP, transfer, production, or provenance.",
            "SELL is exact realized market execution from the validated logger.",
            "Market BUY_PRODUCT events are retained so shed balance is not falsely attributed to SELL alone.",
            "Time-series entries are change points in opponent-minus-self residuals, not causal transitions.",
            "No Action, policy, Representation, Evaluation, Direction, Candidate, or terminal adoption conclusion is inferred.",
        ],
    }

    Path("battle_value_stock_balance_v0_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("BATTLE_VALUE_STOCK_BALANCE_RESULT " + json.dumps({
        "battle_count": len(cases),
        "terminal_absolute": payload["terminal_absolute"],
        "integrity": payload["integrity"],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
