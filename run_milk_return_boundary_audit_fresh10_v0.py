#!/usr/bin/env python3
"""MILK Return Boundary Audit fresh10 v0.

Target:
A = Current D14
B = Seed reopen

This audit follows realized SELL MILK boundaries only and asks whether the
A->B self delta sign is associated with changes in:
- realized MILK units,
- realized unit price,
- market inventory at quote/commit,
- timing,
- pre-sale self MILK stock,
- same-turn market composition.

Observation only. No causal promotion.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import seed_horizon_isolation_probe_v0 as probe
import run_seed_horizon_isolation_fresh10_v0 as horizon

CASES = horizon.CASES
MODES = ("A", "B")
OUT = Path("milk_return_boundary_audit_fresh10_v0_result.json")


def cfgget(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def product_stock(private, item):
    total = int((private.get("shed", {}) or {}).get(item, 0) or 0)
    for inv in private.get("inventories", []) or []:
        if isinstance(inv, dict):
            total += int(inv.get(item, 0) or 0)
    return total


class MilkAudit:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.all_market_events: List[Dict[str, Any]] = []

    def process_market(self, state, env):
        obs0 = state[0].observation
        day = int(getattr(obs0, "day", 0))
        hour = int(getattr(obs0, "hour", 0))
        market = obs0.market
        farms = obs0.farms
        privates = [s.observation.private for s in state]
        board_size = int(cfgget(env.configuration, "boardSize", 10))
        max_orders = max(1, int(cfgget(env.configuration, "maxMarketOrdersPerTurn", 10)))
        hire_mult = int(cfgget(env.configuration, "farmHandCostMult", kg.FARM_HAND_COST_MULT))
        shed_capacity = int(cfgget(env.configuration, "shedCapacity", 100))

        queues = []
        raw_turn_orders = []
        for s in state:
            action = s.action if isinstance(s.action, dict) else {}
            m = action.get("market", []) if isinstance(action, dict) else []
            q = list(m)[:max_orders] if isinstance(m, list) else []
            queues.append(q)
            raw_turn_orders.append(json.loads(json.dumps(q)))

        max_len = max((len(q) for q in queues), default=0)
        event_index = 0

        for order_index in range(max_len):
            order_states = [
                kg._parse_order(q[order_index]) if order_index < len(q) else None
                for q in queues
            ]

            for p, ostate in enumerate(order_states):
                if ostate is None:
                    continue
                op = ostate["type"]
                if op == "HIRE":
                    before = float(farms[p]["money"])
                    kg._do_hire(farms[p], privates[p], board_size, hire_mult)
                    after = float(farms[p]["money"])
                    if after != before:
                        self.all_market_events.append({
                            "player": p, "day": day, "hour": hour,
                            "event_index": event_index, "op": "HIRE",
                            "item": None, "cash_delta": after - before,
                        })
                        event_index += 1
                    order_states[p] = None
                elif op == "BUY_LAND":
                    before = float(farms[p]["money"])
                    kg._do_buy_land(farms[p], board_size)
                    after = float(farms[p]["money"])
                    if after != before:
                        self.all_market_events.append({
                            "player": p, "day": day, "hour": hour,
                            "event_index": event_index, "op": "BUY_LAND",
                            "item": None, "cash_delta": after - before,
                        })
                        event_index += 1
                    order_states[p] = None

            guard = 0
            while True:
                guard += 1
                if guard >= 100000:
                    raise RuntimeError("market loop guard exceeded")

                quoted = [None, None]
                for p, ostate in enumerate(order_states):
                    if ostate is None or ostate["remaining"] <= 0:
                        continue
                    op = ostate["type"]
                    item = ostate["item"]
                    if op == "SELL" and item in kg.PRODUCTS:
                        quoted[p] = (
                            "SELL", item,
                            kg.market_price(item, market["inventory"][item], market.get("params")),
                            ostate,
                        )
                    elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                        quoted[p] = (
                            "BUY_PRODUCT", item,
                            kg.market_price(item, market["inventory"][item] - 1, market.get("params")),
                            ostate,
                        )
                    elif op == "BUY_SEED" and item in kg.CROPS:
                        quoted[p] = ("BUY_SEED", item, kg.CROPS[item]["seed"], ostate)
                    elif op == "BUY_ANIMAL" and item in kg.ANIMALS:
                        quoted[p] = ("BUY_ANIMAL", item, kg.ANIMALS[item]["cost"], ostate)
                    else:
                        order_states[p] = None

                if all(q is None for q in quoted):
                    break

                committed_any = False
                for p, q in enumerate(quoted):
                    if q is None:
                        continue
                    op, item, price, ostate = q

                    cash_before = float(farms[p]["money"])
                    market_inventory_before = int(market["inventory"].get(item, 0) or 0)
                    item_stock_before = product_stock(privates[p], item) if item in kg.PRODUCTS else None
                    milk_stock_before = product_stock(privates[p], "MILK")

                    ok = kg._commit_unit(
                        op, item, price, farms[p], privates[p], market, shed_capacity
                    )
                    cash_after = float(farms[p]["money"])

                    if ok:
                        delta = cash_after - cash_before
                        rec = {
                            "player": p,
                            "day": day,
                            "hour": hour,
                            "event_index": event_index,
                            "op": op,
                            "item": item,
                            "unit_price": float(price),
                            "cash_before": cash_before,
                            "cash_after": cash_after,
                            "cash_delta": delta,
                            "market_inventory_before": market_inventory_before,
                            "market_inventory_after": int(market["inventory"].get(item, 0) or 0),
                            "item_stock_before": item_stock_before,
                            "item_stock_after": (
                                product_stock(privates[p], item)
                                if item in kg.PRODUCTS else None
                            ),
                            "milk_stock_before": milk_stock_before,
                            "milk_stock_after": product_stock(privates[p], "MILK"),
                            "raw_turn_market_orders_self": raw_turn_orders[p],
                            "raw_turn_market_orders_opponent": raw_turn_orders[1 - p],
                        }
                        self.all_market_events.append(rec)
                        if op == "SELL" and item == "MILK":
                            self.events.append(rec)
                        event_index += 1
                        ostate["remaining"] -= 1
                        committed_any = True
                    else:
                        order_states[p] = None

                if not committed_any:
                    break

            kg._refresh_prices(market)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def play(seed, seat, mode):
    configure()
    probe.set_mode(mode)
    probe.reset_telemetry()
    audit = MilkAudit()

    original = kg._process_market
    kg._process_market = audit.process_market
    try:
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[seat] = probe.agent
        env.run(players)
        rewards = [float(x.reward) for x in env.state]
    finally:
        kg._process_market = original

    self_events = [e for e in audit.events if e["player"] == seat]

    by_turn = defaultdict(lambda: {"units": 0, "cash": 0.0, "prices": [], "events": []})
    for e in self_events:
        k = f"D{e['day']}h{e['hour']}"
        by_turn[k]["units"] += 1
        by_turn[k]["cash"] += e["cash_delta"]
        by_turn[k]["prices"].append(e["unit_price"])
        by_turn[k]["events"].append(e)

    total_units = len(self_events)
    total_cash = sum(e["cash_delta"] for e in self_events)
    weighted_avg_price = total_cash / total_units if total_units else None

    post14 = [e for e in self_events if e["day"] >= 14]
    post14_units = len(post14)
    post14_cash = sum(e["cash_delta"] for e in post14)
    post14_avg_price = post14_cash / post14_units if post14_units else None

    return {
        "terminal": {
            "self": rewards[seat],
            "opponent": rewards[1 - seat],
            "margin": rewards[seat] - rewards[1 - seat],
        },
        "milk": {
            "all_units": total_units,
            "all_cash": total_cash,
            "all_avg_realized_price": weighted_avg_price,
            "post14_units": post14_units,
            "post14_cash": post14_cash,
            "post14_avg_realized_price": post14_avg_price,
            "events": self_events,
            "by_turn": dict(sorted(by_turn.items())),
        },
    }


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main():
    cases = []
    for seed, seat in CASES:
        a = play(seed, seat, "A")
        b = play(seed, seat, "B")
        delta_self = b["terminal"]["self"] - a["terminal"]["self"]
        group = "SELF_IMPROVED" if delta_self > 0 else "SELF_WORSE" if delta_self < 0 else "SELF_EQUAL"

        delta_units = b["milk"]["post14_units"] - a["milk"]["post14_units"]
        delta_cash = b["milk"]["post14_cash"] - a["milk"]["post14_cash"]

        a_avg = a["milk"]["post14_avg_realized_price"]
        b_avg = b["milk"]["post14_avg_realized_price"]
        delta_avg_price = (
            None if a_avg is None or b_avg is None else b_avg - a_avg
        )

        first_diff_turn = None
        turns = sorted(set(a["milk"]["by_turn"]) | set(b["milk"]["by_turn"]))
        for t in turns:
            aa = a["milk"]["by_turn"].get(t, {"units": 0, "cash": 0.0, "prices": []})
            bb = b["milk"]["by_turn"].get(t, {"units": 0, "cash": 0.0, "prices": []})
            if aa["units"] != bb["units"] or abs(aa["cash"] - bb["cash"]) > 1e-9 or aa["prices"] != bb["prices"]:
                first_diff_turn = {
                    "timestamp": t,
                    "A": {"units": aa["units"], "cash": aa["cash"], "prices": aa["prices"]},
                    "B": {"units": bb["units"], "cash": bb["cash"], "prices": bb["prices"]},
                }
                break

        cases.append({
            "seed": seed,
            "seat": seat,
            "group": group,
            "delta_terminal_self": delta_self,
            "delta_terminal_margin": b["terminal"]["margin"] - a["terminal"]["margin"],
            "A": a,
            "B": b,
            "milk_delta": {
                "post14_units": delta_units,
                "post14_cash": delta_cash,
                "post14_avg_realized_price": delta_avg_price,
                "first_boundary_difference": first_diff_turn,
            },
        })

    groups = {}
    for group in ("SELF_IMPROVED", "SELF_WORSE"):
        rows = [c for c in cases if c["group"] == group]
        groups[group] = {
            "count": len(rows),
            "delta_terminal_self_mean": mean([c["delta_terminal_self"] for c in rows]),
            "delta_milk_units_mean": mean([c["milk_delta"]["post14_units"] for c in rows]),
            "delta_milk_cash_mean": mean([c["milk_delta"]["post14_cash"] for c in rows]),
            "delta_milk_avg_price_mean": mean([c["milk_delta"]["post14_avg_realized_price"] for c in rows]),
            "cases_with_milk_cash_positive": sum(1 for c in rows if c["milk_delta"]["post14_cash"] > 0),
            "cases_with_milk_cash_negative": sum(1 for c in rows if c["milk_delta"]["post14_cash"] < 0),
            "cases_with_avg_price_positive": sum(
                1 for c in rows
                if c["milk_delta"]["post14_avg_realized_price"] is not None
                and c["milk_delta"]["post14_avg_realized_price"] > 0
            ),
            "cases_with_avg_price_negative": sum(
                1 for c in rows
                if c["milk_delta"]["post14_avg_realized_price"] is not None
                and c["milk_delta"]["post14_avg_realized_price"] < 0
            ),
            "by_seed": {
                str(c["seed"]): {
                    "delta_self": c["delta_terminal_self"],
                    "delta_units": c["milk_delta"]["post14_units"],
                    "delta_cash": c["milk_delta"]["post14_cash"],
                    "delta_avg_price": c["milk_delta"]["post14_avg_realized_price"],
                    "first_boundary_difference": c["milk_delta"]["first_boundary_difference"],
                }
                for c in rows
            },
        }

    result = {
        "schema": "kaggriculture.milk-return-boundary-audit.fresh10.result.v0",
        "group_summary": groups,
        "cases": cases,
        "boundary": [
            "All SELL MILK records are realized successful market units under the public market processor.",
            "Unit price is the actual quote used by the successful commit.",
            "Market inventory is recorded immediately before/after the successful unit commit.",
            "A/B differ only in D14 BUY_SEED suppression.",
            "Improved/worse grouping is retrospective and not a live feature.",
            "A MILK separator here would be an observed association, not proof that MILK caused terminal improvement.",
            "Same-turn market composition is recorded to support later boundary inspection.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("MILK_RETURN_BOUNDARY_AUDIT " + json.dumps({
        "group_summary": groups,
        "cases": [
            {
                "seed": c["seed"],
                "group": c["group"],
                "delta_self": c["delta_terminal_self"],
                "delta_units": c["milk_delta"]["post14_units"],
                "delta_cash": c["milk_delta"]["post14_cash"],
                "delta_avg_price": c["milk_delta"]["post14_avg_realized_price"],
                "first_boundary_difference": c["milk_delta"]["first_boundary_difference"],
            }
            for c in cases
        ],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
