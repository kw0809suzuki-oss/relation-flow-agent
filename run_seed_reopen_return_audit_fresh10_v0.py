#!/usr/bin/env python3
"""Seed Reopen Return Audit fresh10 v0.

Compares only:
A = Current D14
B = D14 Seed reopen

Purpose:
Find the first externally observable economic separator between the 7 self-
improved and 3 self-worsened cases returned by Seed Horizon Isolation v0.

This observer records:
- exact realized market Cash ledger copied from public Kaggriculture rules,
- daily/self checkpoint State,
- physical post-D14 Plant -> Harvest completion,
- A/B terminal deltas.

It does NOT causally pair a SELL unit with a specific seed purchase.
It does NOT infer that any observed separator causes terminal improvement.
"""
from __future__ import annotations

import copy
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import seed_horizon_isolation_probe_v0 as probe
import run_seed_horizon_isolation_fresh10_v0 as horizon
import cross_view_timeline_v0 as cv


CASES = horizon.CASES
MODES = (probe.MODE_CURRENT_D14, probe.MODE_SEED_REOPEN)
OUT = Path("seed_reopen_return_audit_fresh10_v0_result.json")
CHECKPOINTS = ((14, 0), (20, 0), (24, 0), (28, 0), (29, 23))


def cfgget(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class ExactLedger:
    def __init__(self):
        self.ledger = [defaultdict(float), defaultdict(float)]
        self.units = [defaultdict(int), defaultdict(int)]
        self.daily_ledger = [
            defaultdict(lambda: defaultdict(float)),
            defaultdict(lambda: defaultdict(float)),
        ]
        self.daily_units = [
            defaultdict(lambda: defaultdict(int)),
            defaultdict(lambda: defaultdict(int)),
        ]
        self.events: List[Dict[str, Any]] = []

    @staticmethod
    def key(op, item=None):
        return f"{op}:{item}" if item else op

    def process_market(self, state, env):
        obs0 = state[0].observation
        day = int(getattr(obs0, "day", 0))
        hour = int(getattr(obs0, "hour", 0))
        market = obs0.market
        farms = obs0.farms
        privates = [s.observation.private for s in state]
        board_size = int(cfgget(env.configuration, "boardSize", 10))
        max_orders = max(
            1, int(cfgget(env.configuration, "maxMarketOrdersPerTurn", 10))
        )
        hire_mult = int(
            cfgget(env.configuration, "farmHandCostMult", kg.FARM_HAND_COST_MULT)
        )
        shed_capacity = int(cfgget(env.configuration, "shedCapacity", 100))

        queues = []
        for s in state:
            action = s.action if isinstance(s.action, dict) else {}
            m = action.get("market", []) if isinstance(action, dict) else []
            q = list(m) if isinstance(m, list) else []
            queues.append(q[:max_orders])

        max_len = max((len(q) for q in queues), default=0)
        for order_index in range(max_len):
            order_states = []
            for p, q in enumerate(queues):
                order_states.append(
                    kg._parse_order(q[order_index]) if order_index < len(q) else None
                )

            # Atomic orders.
            for p, ostate in enumerate(order_states):
                if ostate is None:
                    continue
                op = ostate["type"]
                if op == "HIRE":
                    before = float(farms[p]["money"])
                    kg._do_hire(
                        farms[p], privates[p], board_size, hire_mult
                    )
                    after = float(farms[p]["money"])
                    delta = after - before
                    if delta != 0:
                        self._record(
                            p, day, hour, "HIRE", None, delta, None
                        )
                    order_states[p] = None
                elif op == "BUY_LAND":
                    before = float(farms[p]["money"])
                    kg._do_buy_land(farms[p], board_size)
                    after = float(farms[p]["money"])
                    delta = after - before
                    if delta != 0:
                        self._record(
                            p, day, hour, "BUY_LAND", None, delta, None
                        )
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
                            "SELL",
                            item,
                            kg.market_price(
                                item,
                                market["inventory"][item],
                                market.get("params"),
                            ),
                            ostate,
                        )
                    elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                        quoted[p] = (
                            "BUY_PRODUCT",
                            item,
                            kg.market_price(
                                item,
                                market["inventory"][item] - 1,
                                market.get("params"),
                            ),
                            ostate,
                        )
                    elif op == "BUY_SEED" and item in kg.CROPS:
                        quoted[p] = (
                            "BUY_SEED",
                            item,
                            kg.CROPS[item]["seed"],
                            ostate,
                        )
                    elif op == "BUY_ANIMAL" and item in kg.ANIMALS:
                        quoted[p] = (
                            "BUY_ANIMAL",
                            item,
                            kg.ANIMALS[item]["cost"],
                            ostate,
                        )
                    else:
                        order_states[p] = None

                if all(q is None for q in quoted):
                    break

                committed_any = False
                for p, q in enumerate(quoted):
                    if q is None:
                        continue
                    op, item, price, ostate = q
                    before = float(farms[p]["money"])
                    ok = kg._commit_unit(
                        op,
                        item,
                        price,
                        farms[p],
                        privates[p],
                        market,
                        shed_capacity,
                    )
                    after = float(farms[p]["money"])
                    if ok:
                        delta = after - before
                        self._record(p, day, hour, op, item, delta, float(price))
                        ostate["remaining"] -= 1
                        committed_any = True
                    else:
                        order_states[p] = None

                if not committed_any:
                    break

            kg._refresh_prices(market)

    def _record(self, p, day, hour, op, item, delta, price):
        k = self.key(op, item)
        self.ledger[p][k] += float(delta)
        self.units[p][k] += 1
        self.daily_ledger[p][day][k] += float(delta)
        self.daily_units[p][day][k] += 1
        self.events.append(
            {
                "player": p,
                "day": day,
                "hour": hour,
                "op": op,
                "item": item,
                "price": price,
                "cash_delta": float(delta),
            }
        )


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def checkpoint_states(steps, seat):
    wanted = set(CHECKPOINTS)
    out = {}
    for row in steps:
        obs = row[seat].get("observation", {}) or {}
        key = (int(obs.get("day", 0) or 0), int(obs.get("hour", 0) or 0))
        if key in wanted:
            s = cv.state_summary(obs, seat)
            out[f"D{key[0]}h{key[1]}"] = {
                k: v
                for k, v in s.items()
                if k != "tiles"
            }
    return out


def ledger_slice(ledger: ExactLedger, player: int, min_day: int) -> Dict[str, Any]:
    events = [
        e for e in ledger.events
        if e["player"] == player and e["day"] >= min_day
    ]
    cash = defaultdict(float)
    units = defaultdict(int)
    for e in events:
        k = ExactLedger.key(e["op"], e["item"])
        cash[k] += float(e["cash_delta"])
        units[k] += 1

    sell_cash = sum(v for k, v in cash.items() if k.startswith("SELL:"))
    buy_seed_cost = -sum(v for k, v in cash.items() if k.startswith("BUY_SEED:"))
    operating_cost = -sum(
        v
        for k, v in cash.items()
        if k in ("BUY_PRODUCT:WHEAT", "BUY_PRODUCT:FERTILIZER")
    )
    structural_cost = -sum(
        v
        for k, v in cash.items()
        if k in ("BUY_LAND", "BUY_ANIMAL:COW", "BUY_ANIMAL:SHEEP", "BUY_ANIMAL:GOOSE")
    )
    hire_cost = -cash.get("HIRE", 0.0)

    return {
        "cash_by_order": dict(sorted(cash.items())),
        "units_by_order": dict(sorted(units.items())),
        "sell_cash": sell_cash,
        "buy_seed_cost": buy_seed_cost,
        "operating_cost": operating_cost,
        "structural_cost": structural_cost,
        "hire_cost": hire_cost,
        "net_market_cash": sum(cash.values()),
        "surplus_after_operating_and_seed": sell_cash - operating_cost - buy_seed_cost,
        "boundary": (
            "Surplus is an accounting residual over realized market events, "
            "not a causal attribution of SELL proceeds to later purchases."
        ),
    }


def play(seed, seat, mode):
    configure()
    probe.set_mode(mode)
    probe.reset_telemetry()
    exact = ExactLedger()

    original_market = kg._process_market
    kg._process_market = exact.process_market
    try:
        env = make("kaggriculture", configuration={"seed": seed}, debug=False)
        initial = [
            float(env.state[i].observation.farms[i].money)
            for i in (0, 1)
        ]
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[seat] = probe.agent
        env.run(players)
        terminal = [float(x.reward) for x in env.state]
        steps = horizon.extract_replay(env)
    finally:
        kg._process_market = original_market

    reconstruction = []
    for p in (0, 1):
        net = sum(exact.ledger[p].values())
        reconstructed = initial[p] + net
        reconstruction.append(
            {
                "player": p,
                "initial": initial[p],
                "net": net,
                "reconstructed": reconstructed,
                "terminal": terminal[p],
                "error": reconstructed - terminal[p],
            }
        )

    if any(abs(x["error"]) > 1e-9 for x in reconstruction):
        raise RuntimeError(
            f"cash reconstruction failed seed={seed} mode={mode}: {reconstruction}"
        )

    return {
        "mode": mode,
        "terminal": {
            "self": terminal[seat],
            "opponent": terminal[1 - seat],
            "margin": terminal[seat] - terminal[1 - seat],
        },
        "reconstruction": reconstruction,
        "post_d14_cash_flow": ledger_slice(exact, seat, 14),
        "post_d20_cash_flow": ledger_slice(exact, seat, 20),
        "opponent_post_d14_cash_flow": ledger_slice(exact, 1 - seat, 14),
        "physical": horizon.plant_harvest_audit(steps, seat),
        "checkpoints": checkpoint_states(steps, seat),
        "filter": {
            k: v
            for k, v in probe.get_telemetry().items()
            if k in (
                "native_seed_requests_after_d14",
                "seed_requests_allowed_after_d14",
                "seed_requests_suppressed_after_d14",
                "changed_turns",
                "removed_orders",
            )
        },
    }


def delta_dict(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    out = {}
    for k in sorted(set(a) | set(b)):
        d = float(b.get(k, 0.0)) - float(a.get(k, 0.0))
        if abs(d) > 1e-9:
            out[k] = d
    return out


def case_delta(a, b):
    return {
        "terminal": {
            "self": b["terminal"]["self"] - a["terminal"]["self"],
            "opponent": b["terminal"]["opponent"] - a["terminal"]["opponent"],
            "margin": b["terminal"]["margin"] - a["terminal"]["margin"],
        },
        "post_d14_cash_flow": {
            "sell_cash": b["post_d14_cash_flow"]["sell_cash"] - a["post_d14_cash_flow"]["sell_cash"],
            "buy_seed_cost": b["post_d14_cash_flow"]["buy_seed_cost"] - a["post_d14_cash_flow"]["buy_seed_cost"],
            "operating_cost": b["post_d14_cash_flow"]["operating_cost"] - a["post_d14_cash_flow"]["operating_cost"],
            "hire_cost": b["post_d14_cash_flow"]["hire_cost"] - a["post_d14_cash_flow"]["hire_cost"],
            "net_market_cash": b["post_d14_cash_flow"]["net_market_cash"] - a["post_d14_cash_flow"]["net_market_cash"],
            "surplus_after_operating_and_seed": (
                b["post_d14_cash_flow"]["surplus_after_operating_and_seed"]
                - a["post_d14_cash_flow"]["surplus_after_operating_and_seed"]
            ),
            "cash_by_order": delta_dict(
                a["post_d14_cash_flow"]["cash_by_order"],
                b["post_d14_cash_flow"]["cash_by_order"],
            ),
            "units_by_order": delta_dict(
                a["post_d14_cash_flow"]["units_by_order"],
                b["post_d14_cash_flow"]["units_by_order"],
            ),
        },
        "post_d20_cash_flow": {
            "sell_cash": b["post_d20_cash_flow"]["sell_cash"] - a["post_d20_cash_flow"]["sell_cash"],
            "buy_seed_cost": b["post_d20_cash_flow"]["buy_seed_cost"] - a["post_d20_cash_flow"]["buy_seed_cost"],
            "operating_cost": b["post_d20_cash_flow"]["operating_cost"] - a["post_d20_cash_flow"]["operating_cost"],
            "net_market_cash": b["post_d20_cash_flow"]["net_market_cash"] - a["post_d20_cash_flow"]["net_market_cash"],
        },
        "physical": {
            "post_d14_activated": b["physical"]["post_d14_activated"] - a["physical"]["post_d14_activated"],
            "post_d14_harvested": b["physical"]["post_d14_harvested"] - a["physical"]["post_d14_harvested"],
            "day20_plus_activated": b["physical"]["day20_plus_activated"] - a["physical"]["day20_plus_activated"],
            "day20_plus_harvested": b["physical"]["day20_plus_harvested"] - a["physical"]["day20_plus_harvested"],
        },
    }


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def group_summary(cases, group):
    rows = [c for c in cases if c["judge_group"] == group]
    if not rows:
        return {}
    fields = [
        ("delta_self", lambda c: c["delta"]["terminal"]["self"]),
        ("delta_opponent", lambda c: c["delta"]["terminal"]["opponent"]),
        ("delta_margin", lambda c: c["delta"]["terminal"]["margin"]),
        ("delta_sell_cash_d14", lambda c: c["delta"]["post_d14_cash_flow"]["sell_cash"]),
        ("extra_seed_cost_d14", lambda c: c["delta"]["post_d14_cash_flow"]["buy_seed_cost"]),
        ("delta_operating_cost_d14", lambda c: c["delta"]["post_d14_cash_flow"]["operating_cost"]),
        ("delta_net_market_cash_d14", lambda c: c["delta"]["post_d14_cash_flow"]["net_market_cash"]),
        ("delta_surplus_after_operating_seed_d14", lambda c: c["delta"]["post_d14_cash_flow"]["surplus_after_operating_and_seed"]),
        ("delta_sell_cash_d20", lambda c: c["delta"]["post_d20_cash_flow"]["sell_cash"]),
        ("extra_seed_cost_d20", lambda c: c["delta"]["post_d20_cash_flow"]["buy_seed_cost"]),
        ("delta_operating_cost_d20", lambda c: c["delta"]["post_d20_cash_flow"]["operating_cost"]),
        ("delta_post14_activated", lambda c: c["delta"]["physical"]["post_d14_activated"]),
        ("delta_post14_harvested", lambda c: c["delta"]["physical"]["post_d14_harvested"]),
        ("delta_day20_activated", lambda c: c["delta"]["physical"]["day20_plus_activated"]),
        ("delta_day20_harvested", lambda c: c["delta"]["physical"]["day20_plus_harvested"]),
    ]
    return {
        "count": len(rows),
        **{name: mean([fn(c) for c in rows]) for name, fn in fields},
        "by_seed": {
            str(c["seed"]): {
                "delta_self": c["delta"]["terminal"]["self"],
                "delta_margin": c["delta"]["terminal"]["margin"],
                "delta_sell_cash_d14": c["delta"]["post_d14_cash_flow"]["sell_cash"],
                "extra_seed_cost_d14": c["delta"]["post_d14_cash_flow"]["buy_seed_cost"],
                "delta_operating_cost_d14": c["delta"]["post_d14_cash_flow"]["operating_cost"],
                "delta_surplus_after_operating_seed_d14": c["delta"]["post_d14_cash_flow"]["surplus_after_operating_and_seed"],
                "delta_post14_harvested": c["delta"]["physical"]["post_d14_harvested"],
            }
            for c in rows
        },
    }


def main():
    cases = []
    for seed, seat in CASES:
        a = play(seed, seat, "A")
        b = play(seed, seat, "B")
        delta = case_delta(a, b)
        cases.append(
            {
                "seed": seed,
                "seat": seat,
                "judge_group": (
                    "SELF_IMPROVED"
                    if delta["terminal"]["self"] > 0
                    else "SELF_WORSE"
                    if delta["terminal"]["self"] < 0
                    else "SELF_EQUAL"
                ),
                "A": a,
                "B": b,
                "delta": delta,
            }
        )

    result = {
        "schema": "kaggriculture.seed-reopen-return-audit.fresh10.result.v0",
        "cases": cases,
        "group_summary": {
            "SELF_IMPROVED": group_summary(cases, "SELF_IMPROVED"),
            "SELF_WORSE": group_summary(cases, "SELF_WORSE"),
        },
        "boundary": [
            "A/B share the frozen body and differ only in D14 BUY_SEED suppression.",
            "Exact Cash ledger reconstructs terminal Cash from successfully executed market orders.",
            "Item-level SELL and BUY deltas are accounting observations, not causal token-level lineage.",
            "Physical Plant/Harvest deltas are actual-path observations but are not attributed to particular purchased seed units after fungibility.",
            "Improved/worse grouping is retrospective and must not be used as a live feature.",
            "Any separator found in 7 vs 3 cases is a candidate only and requires new-Battle validation.",
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "group_summary": result["group_summary"],
        "cases": [
            {
                "seed": c["seed"],
                "group": c["judge_group"],
                "delta_self": c["delta"]["terminal"]["self"],
                "delta_margin": c["delta"]["terminal"]["margin"],
                "delta_sell_cash_d14": c["delta"]["post_d14_cash_flow"]["sell_cash"],
                "extra_seed_cost_d14": c["delta"]["post_d14_cash_flow"]["buy_seed_cost"],
                "delta_operating_cost_d14": c["delta"]["post_d14_cash_flow"]["operating_cost"],
                "delta_surplus_d14": c["delta"]["post_d14_cash_flow"]["surplus_after_operating_and_seed"],
                "delta_harvested": c["delta"]["physical"]["post_d14_harvested"],
            }
            for c in cases
        ],
    }
    print(
        "SEED_REOPEN_RETURN_AUDIT "
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    )


if __name__ == "__main__":
    main()
