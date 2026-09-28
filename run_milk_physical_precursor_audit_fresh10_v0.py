#!/usr/bin/env python3
"""MILK Physical Precursor Audit fresh10 v0.

A = Current D14
B = Seed reopen

Starting from the first realized SELL MILK boundary difference, trace exactly
one physical pipeline upstream:

COW yield -> HARVEST/carry -> DROP or day-boundary shed -> SELL-ready shed -> SELL

The observer records two state surfaces per turn:
- pre_unit: observation seen by the self agent before unit actions
- pre_market: state after unit actions and before market resolution

Public-rule boundary:
SELL consumes private["shed"][MILK] only. Carried MILK is not sell-ready until
it reaches the shed.

Observation only. No causal promotion.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import seed_horizon_isolation_probe_v0 as probe
import run_seed_horizon_isolation_fresh10_v0 as horizon
import run_milk_return_boundary_audit_fresh10_v0 as milk_boundary

CASES = horizon.CASES
OUT = Path("milk_physical_precursor_audit_fresh10_v0_result.json")


def cfgget(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def farm_milk_state(farm: Dict[str, Any], private: Dict[str, Any]) -> Dict[str, Any]:
    shed_milk = int((private.get("shed", {}) or {}).get("MILK", 0) or 0)
    invs = private.get("inventories", []) or []
    carried_by_actor = [
        int((inv or {}).get("MILK", 0) or 0) if isinstance(inv, dict) else 0
        for inv in invs
    ]
    carried_milk = sum(carried_by_actor)

    cow_yield_total = 0
    cow_ready_count = 0
    cow_count = 0
    cow_tiles = []
    for y, row in enumerate(farm.get("tiles", []) or []):
        for x, tile in enumerate(row or []):
            if not isinstance(tile, dict) or tile.get("animal") != "COW":
                continue
            cow_count += 1
            units = int(tile.get("yield_units", 0) or 0)
            cow_yield_total += units
            if units > 0:
                cow_ready_count += 1
            cow_tiles.append({
                "position": [x, y],
                "placed_day": int(tile.get("placed_day", 0) or 0),
                "yield_units": units,
            })

    return {
        "cow_count": cow_count,
        "cow_yield_total": cow_yield_total,
        "cow_ready_count": cow_ready_count,
        "cow_tiles": cow_tiles,
        "carried_milk": carried_milk,
        "carried_milk_by_actor": carried_by_actor,
        "shed_milk": shed_milk,
        "sell_ready_milk": shed_milk,
        "physical_milk_total": cow_yield_total + carried_milk + shed_milk,
    }


def unit_action_detail(obs: Dict[str, Any], action: Dict[str, Any]) -> List[Dict[str, Any]]:
    player = int(obs.get("player", 0) or 0)
    farms = obs.get("farms", []) or []
    farm = farms[player] if player < len(farms) else {}
    private = obs.get("private", {}) or {}
    invs = private.get("inventories", []) or []

    positions = [farm.get("farmer")]
    positions.extend(farm.get("hands", []) or [])

    actions = [action.get("farmer", ["PASS"])]
    actions.extend(action.get("hands", []) or [])

    out = []
    for idx, act in enumerate(actions):
        if not isinstance(act, list) or not act:
            act = ["PASS"]
        pos = positions[idx] if idx < len(positions) else None
        inv = invs[idx] if idx < len(invs) and isinstance(invs[idx], dict) else {}
        tile = None
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            x, y = int(pos[0]), int(pos[1])
            try:
                tile = farm["tiles"][y][x]
            except Exception:
                tile = None
        out.append({
            "actor_index": idx,
            "actor": "farmer" if idx == 0 else f"hand:{idx-1}",
            "position": list(pos) if isinstance(pos, (list, tuple)) else None,
            "action": list(act),
            "milk_carried_before": int(inv.get("MILK", 0) or 0),
            "standing_cow_yield_before": (
                int(tile.get("yield_units", 0) or 0)
                if isinstance(tile, dict) and tile.get("animal") == "COW"
                else None
            ),
        })
    return out


def milk_market_request(action: Dict[str, Any]) -> List[Any]:
    rows = []
    for order in action.get("market", []) or []:
        if (
            isinstance(order, list)
            and len(order) >= 2
            and order[0] == "SELL"
            and order[1] == "MILK"
        ):
            rows.append(list(order))
    return rows


def key(day: int, hour: int) -> str:
    return f"D{day}h{hour}"


def compact_physical(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cow_count": s["cow_count"],
        "cow_yield_total": s["cow_yield_total"],
        "cow_ready_count": s["cow_ready_count"],
        "carried_milk": s["carried_milk"],
        "shed_milk": s["shed_milk"],
        "sell_ready_milk": s["sell_ready_milk"],
        "physical_milk_total": s["physical_milk_total"],
    }


def physical_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return compact_physical(a) == compact_physical(b)


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def play(seed: int, seat: int, mode: str) -> Dict[str, Any]:
    configure()
    probe.set_mode(mode)
    probe.reset_telemetry()

    exact = milk_boundary.MilkAudit()
    pre_unit_rows: Dict[str, Any] = {}
    pre_market_rows: Dict[str, Any] = {}

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed_agent(obs):
        action = probe.agent(obs)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        player = int(obs.get("player", seat) or seat)
        farm = (obs.get("farms", []) or [])[player]
        private = obs.get("private", {}) or {}
        pre_unit_rows[key(day, hour)] = {
            "day": day,
            "hour": hour,
            "state": farm_milk_state(farm, private),
            "unit_actions": unit_action_detail(obs, action),
            "sell_milk_request": milk_market_request(action),
            "all_market_orders": json.loads(
                json.dumps(action.get("market", []) if isinstance(action, dict) else [])
            ),
        }
        return action

    def observed_market(state, env_obj):
        obs0 = state[0].observation
        day = int(getattr(obs0, "day", 0))
        hour = int(getattr(obs0, "hour", 0))
        farm = obs0.farms[seat]
        private = state[seat].observation.private
        market = obs0.market
        pre_market_rows[key(day, hour)] = {
            "day": day,
            "hour": hour,
            "state": farm_milk_state(farm, private),
            "market_inventory_milk": int(market["inventory"].get("MILK", 0) or 0),
            "market_price_milk": float((market.get("prices", {}) or {}).get("MILK", 0) or 0),
        }
        return exact.process_market(state, env_obj)

    original_market = kg._process_market
    kg._process_market = observed_market
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[seat] = observed_agent
        env.run(players)
        rewards = [float(x.reward) for x in env.state]
    finally:
        kg._process_market = original_market

    realized = [e for e in exact.events if e["player"] == seat]
    realized_by_turn = defaultdict(list)
    for e in realized:
        realized_by_turn[key(e["day"], e["hour"])].append(e)

    return {
        "terminal": {
            "self": rewards[seat],
            "opponent": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat],
        },
        "pre_unit": pre_unit_rows,
        "pre_market": pre_market_rows,
        "realized_milk_sell_by_turn": dict(realized_by_turn),
    }


def first_realized_sell_difference(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any] | None:
    turns = sorted(
        set(a["realized_milk_sell_by_turn"]) | set(b["realized_milk_sell_by_turn"]),
        key=lambda t: tuple(map(int, t[1:].replace("h", " ").split())),
    )
    for t in turns:
        aa = a["realized_milk_sell_by_turn"].get(t, [])
        bb = b["realized_milk_sell_by_turn"].get(t, [])
        sig_a = [(x["cash_delta"], x["unit_price"], x["market_inventory_before"]) for x in aa]
        sig_b = [(x["cash_delta"], x["unit_price"], x["market_inventory_before"]) for x in bb]
        if sig_a != sig_b:
            return {"timestamp": t, "A": aa, "B": bb}
    return None


def ordered_timestamps(rows: Dict[str, Any]) -> List[str]:
    return sorted(
        rows,
        key=lambda t: tuple(map(int, t[1:].replace("h", " ").split())),
    )


def physical_difference_trace(a: Dict[str, Any], b: Dict[str, Any], until: str) -> Dict[str, Any]:
    all_turns = sorted(
        set(a["pre_unit"]) | set(b["pre_unit"]),
        key=lambda t: tuple(map(int, t[1:].replace("h", " ").split())),
    )
    until_pair = tuple(map(int, until[1:].replace("h", " ").split()))
    all_turns = [
        t for t in all_turns
        if tuple(map(int, t[1:].replace("h", " ").split())) <= until_pair
    ]

    first = None
    last_equal_before_first = None
    previous_equal = None
    for t in all_turns:
        ra = a["pre_unit"].get(t)
        rb = b["pre_unit"].get(t)
        if not ra or not rb:
            continue
        eq = physical_equal(ra["state"], rb["state"])
        if eq:
            previous_equal = t
        elif first is None:
            first = {
                "timestamp": t,
                "last_equal_timestamp": previous_equal,
                "A": compact_physical(ra["state"]),
                "B": compact_physical(rb["state"]),
            }
            break

    # Nearest physical equality -> difference transition before SELL boundary.
    last_equal = None
    latest_diff_start = None
    in_diff = False
    for t in all_turns:
        ra = a["pre_unit"].get(t)
        rb = b["pre_unit"].get(t)
        if not ra or not rb:
            continue
        eq = physical_equal(ra["state"], rb["state"])
        if eq:
            last_equal = t
            in_diff = False
        else:
            if not in_diff:
                latest_diff_start = {
                    "timestamp": t,
                    "last_equal_timestamp": last_equal,
                    "A": compact_physical(ra["state"]),
                    "B": compact_physical(rb["state"]),
                }
            in_diff = True

    return {
        "first_physical_difference": first,
        "latest_difference_run_start_before_sell": latest_diff_start,
    }


def boundary_view(a: Dict[str, Any], b: Dict[str, Any], t: str) -> Dict[str, Any]:
    return {
        "timestamp": t,
        "A": {
            "pre_unit": a["pre_unit"].get(t),
            "pre_market": a["pre_market"].get(t),
            "realized_sell": a["realized_milk_sell_by_turn"].get(t, []),
        },
        "B": {
            "pre_unit": b["pre_unit"].get(t),
            "pre_market": b["pre_market"].get(t),
            "realized_sell": b["realized_milk_sell_by_turn"].get(t, []),
        },
    }


def classify_boundary(view: Dict[str, Any]) -> Dict[str, Any]:
    apm = (view["A"]["pre_market"] or {}).get("state", {})
    bpm = (view["B"]["pre_market"] or {}).get("state", {})
    au = (view["A"]["pre_unit"] or {}).get("state", {})
    bu = (view["B"]["pre_unit"] or {}).get("state", {})

    sell_ready_equal = apm.get("sell_ready_milk") == bpm.get("sell_ready_milk")
    pre_unit_shed_equal = au.get("shed_milk") == bu.get("shed_milk")
    physical_equal_pre_unit = bool(au and bu and physical_equal(au, bu))
    physical_equal_pre_market = bool(apm and bpm and physical_equal(apm, bpm))

    if not sell_ready_equal:
        label = "SELL_READY_AVAILABILITY_DIFFERS"
    else:
        a_sell = view["A"]["realized_sell"]
        b_sell = view["B"]["realized_sell"]
        a_req = (view["A"]["pre_unit"] or {}).get("sell_milk_request", [])
        b_req = (view["B"]["pre_unit"] or {}).get("sell_milk_request", [])
        if a_req != b_req or bool(a_sell) != bool(b_sell):
            label = "SELL_TIMING_OR_REQUEST_DIFFERS_WITH_EQUAL_READY_STOCK"
        else:
            label = "PRICE_MARKET_STATE_DIFFERS_WITH_EQUAL_READY_STOCK"

    return {
        "label": label,
        "sell_ready_equal_pre_market": sell_ready_equal,
        "pre_unit_shed_equal": pre_unit_shed_equal,
        "physical_equal_pre_unit": physical_equal_pre_unit,
        "physical_equal_pre_market": physical_equal_pre_market,
    }


def main():
    cases = []
    for seed, seat in CASES:
        a = play(seed, seat, "A")
        b = play(seed, seat, "B")
        delta_self = b["terminal"]["self"] - a["terminal"]["self"]
        group = (
            "SELF_IMPROVED" if delta_self > 0
            else "SELF_WORSE" if delta_self < 0
            else "SELF_EQUAL"
        )

        sell_diff = first_realized_sell_difference(a, b)
        if sell_diff is None:
            precursor = None
            view = None
            classification = None
        else:
            t = sell_diff["timestamp"]
            precursor = physical_difference_trace(a, b, t)
            view = boundary_view(a, b, t)
            classification = classify_boundary(view)

        cases.append({
            "seed": seed,
            "seat": seat,
            "group": group,
            "delta_terminal_self": delta_self,
            "first_realized_milk_sell_difference": sell_diff,
            "physical_precursor": precursor,
            "boundary_view": view,
            "classification": classification,
        })

    groups = {}
    for group in ("SELF_IMPROVED", "SELF_WORSE"):
        rows = [c for c in cases if c["group"] == group]
        labels = defaultdict(int)
        for c in rows:
            if c["classification"]:
                labels[c["classification"]["label"]] += 1
        groups[group] = {
            "count": len(rows),
            "classification_counts": dict(sorted(labels.items())),
            "by_seed": {
                str(c["seed"]): {
                    "delta_self": c["delta_terminal_self"],
                    "sell_boundary": (
                        c["first_realized_milk_sell_difference"]["timestamp"]
                        if c["first_realized_milk_sell_difference"] else None
                    ),
                    "classification": (
                        c["classification"]["label"] if c["classification"] else None
                    ),
                    "first_physical_difference": (
                        c["physical_precursor"]["first_physical_difference"]
                        if c["physical_precursor"] else None
                    ),
                    "latest_difference_run_start_before_sell": (
                        c["physical_precursor"]["latest_difference_run_start_before_sell"]
                        if c["physical_precursor"] else None
                    ),
                }
                for c in rows
            },
        }

    result = {
        "schema": "kaggriculture.milk-physical-precursor-audit.fresh10.result.v0",
        "group_summary": groups,
        "cases": cases,
        "boundary": [
            "SELL MILK consumes shed MILK only under the public rule; carried MILK is not sell-ready.",
            "pre_unit is the live observation seen by the self agent before unit actions.",
            "pre_market is the exact environment state after unit actions and before market resolution.",
            "Realized SELL records come from successful public-rule market commits.",
            "A/B differ only in D14 BUY_SEED suppression.",
            "Physical equality/difference is restricted to COW count/yield, carried MILK, shed MILK, and total physical MILK.",
            "The first/nearest physical separator is descriptive chronology, not causal proof.",
            "Improved/worse grouping is retrospective and not available to the live agent.",
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("MILK_PHYSICAL_PRECURSOR_AUDIT " + json.dumps({
        "group_summary": groups,
        "cases": [
            {
                "seed": c["seed"],
                "group": c["group"],
                "delta_self": c["delta_terminal_self"],
                "sell_boundary": (
                    c["first_realized_milk_sell_difference"]["timestamp"]
                    if c["first_realized_milk_sell_difference"] else None
                ),
                "classification": (
                    c["classification"]["label"] if c["classification"] else None
                ),
                "first_physical_difference": (
                    c["physical_precursor"]["first_physical_difference"]["timestamp"]
                    if c["physical_precursor"] and c["physical_precursor"]["first_physical_difference"]
                    else None
                ),
                "latest_diff_start": (
                    c["physical_precursor"]["latest_difference_run_start_before_sell"]["timestamp"]
                    if c["physical_precursor"] and c["physical_precursor"]["latest_difference_run_start_before_sell"]
                    else None
                ),
            }
            for c in cases
        ],
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
