#!/usr/bin/env python3
"""Battle Value Stock Balance v0.

Observation-only replay for the fixed five-Battle Day20->24 window.

Records public-world stock location facts at every market turn:
- shed product quantities before and after market processing
- carried product quantities (sum of private inventories) before and after
- per-inventory carried quantities, without assigning semantic ownership
- exact realized SELL events from the validated market logger
- all exact market events for accounting context

No source/provenance claim is made for stock changes. No harvest, transfer,
Action, policy, Representation, Evaluation, Direction, or Candidate is inferred.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED = int(os.environ["BATTLE_SEED"])
SEAT = int(os.environ["BATTLE_SEAT"])
OUT = Path(f"battle_value_stock_balance_v0_{SEED}_seat{SEAT}.json")

market_turns = []
sell_events = []
market_events = []


def plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    if hasattr(v, "items"):
        try:
            return {str(k): plain(x) for k, x in v.items()}
        except Exception:
            pass
    return str(v)


def getv(x, key, default=None):
    if isinstance(x, dict):
        return x.get(key, default)
    try:
        return getattr(x, key)
    except Exception:
        return default


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"
    body_only.reset_telemetry()


def _qty_map(src):
    src = src if isinstance(src, dict) else {}
    return {item: int(src.get(item, 0) or 0) for item in econ.PRODUCTS}


def side_stock_snapshot(obs):
    player = int(obs["player"])
    farm = obs["farms"][player]
    private = obs.get("private", {}) or {}

    shed = _qty_map(private.get("shed", {}) or {})

    carried_rows = []
    carried_total = {item: 0 for item in econ.PRODUCTS}
    for idx, inv in enumerate(private.get("inventories", []) or []):
        row = _qty_map(inv if isinstance(inv, dict) else {})
        carried_rows.append({"inventory_index": idx, "by_item": row})
        for item in econ.PRODUCTS:
            carried_total[item] += row[item]

    on_hand = {
        item: shed[item] + carried_total[item]
        for item in econ.PRODUCTS
    }

    return {
        "cash": float(farm.get("money", 0) or 0),
        "shed_by_item": shed,
        "carried_by_item": carried_total,
        "on_hand_by_item": on_hand,
        "carried_inventories": carried_rows,
    }


def measured_market_with_stock_balance(state, env):
    obs0 = plain(getv(state[0], "observation"))
    if not isinstance(obs0, dict):
        return exact.measured_process_market(state, env)

    day = int(obs0.get("day", 0) or 0)
    hour = int(obs0.get("hour", 0) or 0)
    t = day * 24 + hour
    in_window = (20 * 24 <= t <= 24 * 24)

    if in_window:
        before = []
        for p in (0, 1):
            op = plain(getv(state[p], "observation"))
            before.append(side_stock_snapshot(op))
    else:
        before = None

    before_n = len(exact.events)
    exact.measured_process_market(state, env)
    new_events = [plain(e) for e in exact.events[before_n:]]

    for e in new_events:
        e["day"] = day
        e["hour"] = hour
        if 20 * 24 <= t < 24 * 24:
            market_events.append(e)
            if e.get("op") == "SELL":
                sell_events.append(e)

    if in_window:
        after = []
        for p in (0, 1):
            op = plain(getv(state[p], "observation"))
            after.append(side_stock_snapshot(op))

        turn_sells = [
            e for e in new_events
            if e.get("op") == "SELL" and 20 * 24 <= t < 24 * 24
        ]
        market_turns.append({
            "day": day,
            "hour": hour,
            "before": before,
            "after": after,
            "sell_events": turn_sells,
        })


def main():
    configure()
    market_turns.clear()
    sell_events.clear()
    market_events.clear()
    exact.ledger = [defaultdict(float), defaultdict(float)]
    exact.units = [defaultdict(int), defaultdict(int)]
    exact.events = []

    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    original_market = kg._process_market
    kg._process_market = measured_market_with_stock_balance
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[SEAT] = body_only.agent
        env.run(players)
    finally:
        kg._process_market = original_market

    rewards = [float(x.reward) for x in env.state]
    payload = {
        "schema": "kaggriculture.strong-origin-v2.battle-value-stock-balance.v0",
        "seed": SEED,
        "seat": SEAT,
        "terminal": {
            "self": rewards[SEAT],
            "opponent": rewards[1 - SEAT],
            "margin": rewards[SEAT] - rewards[1 - SEAT],
        },
        "surface": {
            "start_day": 20,
            "end_day": 24,
            "end_exclusive_for_sell": True,
        },
        "market_turns": market_turns,
        "sell_events": sell_events,
        "market_events": market_events,
        "boundary": [
            "shed_by_item is read directly from private.shed.",
            "carried_by_item is the sum of private.inventories by item; carried_inventories preserves each inventory slot separately without assigning a semantic owner.",
            "on_hand_by_item is shed + carried only; it is not labeled harvested, sellable, produced, or sourced.",
            "before/after snapshots bracket public market processing at the same turn.",
            "SELL events are exact realized market events from the previously validated logging-equivalent public market processor.",
            "All market events are retained because non-SELL market operations can also change stock or Cash.",
            "The Day24 h0 snapshot is retained as an endpoint; SELL aggregation remains Day20 h0 inclusive to Day24 h0 exclusive.",
            "No stock change is attributed to harvest, DROP, carried-to-shed transfer, or any other source without a separate observation.",
            "No Action, policy, Representation, Evaluation, Direction, Candidate, or causal diagnosis is introduced.",
        ],
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "BATTLE_VALUE_STOCK_BALANCE "
        + json.dumps(
            {
                "seed": SEED,
                "seat": SEAT,
                "market_turns": len(market_turns),
                "sell_events": len(sell_events),
                "market_events": len(market_events),
                "terminal": payload["terminal"],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
