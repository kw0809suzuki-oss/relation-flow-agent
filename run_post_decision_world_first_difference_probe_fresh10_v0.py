#!/usr/bin/env python3
"""Post-decision World First-Difference Probe fresh10 v0.

Question:
For cases where the current MILK market snapshot and the previous 6-turn raw
MILK market history are identical at the last compact-MILK-equal decision
point, what is the first externally observed downstream World difference after
the known MILK physical stage divergence?

Scope:
- matched-current + matched-history cases only
- start strictly after the first compact MILK physical difference
- stop at the first realized SELL MILK boundary difference
- compare raw downstream economic/world surfaces
- return ALL difference categories present at the earliest differing timestamp

Known self MILK COW/Carry stage difference and self unit-action difference are
not used as candidate downstream events; they were already established by
earlier probes.
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
import run_milk_physical_precursor_audit_fresh10_v0 as phys
import run_milk_market_raw_history_presence_probe_fresh10_v0 as rawhist

OUT = Path("post_decision_world_first_difference_probe_fresh10_v0_result.json")
CASES = horizon.CASES
HISTORY_WINDOW = 6


def tp(t: str) -> Tuple[int, int]:
    return tuple(map(int, t[1:].replace("h", " ").split()))


def key(day: int, hour: int) -> str:
    return f"D{day}h{hour}"


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"


def compact_map(m: Any) -> Dict[str, Any]:
    if not isinstance(m, dict):
        return {}
    out = {}
    for k, v in sorted(m.items()):
        if isinstance(v, (int, float, str, bool)) or v is None:
            out[str(k)] = v
        else:
            out[str(k)] = horizon.plain(v)
    return out


def carried_aggregate(private: Dict[str, Any], exclude_milk: bool = False) -> Dict[str, int]:
    out = defaultdict(int)
    for inv in private.get("inventories", []) or []:
        if not isinstance(inv, dict):
            continue
        for item, n in inv.items():
            if exclude_milk and item == "MILK":
                continue
            n = int(n or 0)
            if n:
                out[str(item)] += n
    return dict(sorted(out.items()))


def public_market_snapshot(market: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "inventory": compact_map(market.get("inventory", {}) or {}),
        "prices": compact_map(market.get("prices", {}) or {}),
    }


def successful_event_signature(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for e in events:
        out.append({
            "player": int(e["player"]),
            "op": e["op"],
            "item": e["item"],
            "cash_delta": float(e["cash_delta"]),
            "unit_price": (
                None if e.get("unit_price") is None else float(e["unit_price"])
            ),
            "market_inventory_before": (
                None
                if e.get("market_inventory_before") is None
                else int(e["market_inventory_before"])
            ),
        })
    return out


def play(seed: int, seat: int, mode: str) -> Dict[str, Any]:
    configure()
    probe.set_mode(mode)
    probe.reset_telemetry()

    exact = milk_boundary.MilkAudit()
    rows: Dict[str, Dict[str, Any]] = {}

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed_agent(obs):
        action = probe.agent(obs)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        t = key(day, hour)
        rows.setdefault(t, {})
        rows[t]["self_action"] = horizon.plain(action)
        return action

    original_market = kg._process_market

    def observed_market(state, env_obj):
        obs0 = state[0].observation
        day = int(getattr(obs0, "day", 0))
        hour = int(getattr(obs0, "hour", 0))
        t = key(day, hour)

        self_private = state[seat].observation.private
        opp = 1 - seat
        opp_private = state[opp].observation.private
        market = obs0.market

        before_n = len(exact.all_market_events)

        rows.setdefault(t, {})
        rows[t]["pre_market"] = {
            "public_market": public_market_snapshot(market),
            "self_cash": float(obs0.farms[seat]["money"]),
            "opponent_cash": float(obs0.farms[opp]["money"]),
            "self_shed": compact_map(self_private.get("shed", {}) or {}),
            "opponent_shed": compact_map(opp_private.get("shed", {}) or {}),
            # MILK Carry is excluded because the known COW->Carry difference is
            # the already-established upstream separator.
            "self_non_milk_carry": carried_aggregate(
                self_private, exclude_milk=True
            ),
            "opponent_carry": carried_aggregate(opp_private, exclude_milk=False),
            "self_sell_ready_milk": int(
                (self_private.get("shed", {}) or {}).get("MILK", 0) or 0
            ),
            "opponent_action": horizon.plain(
                state[opp].action if isinstance(state[opp].action, dict) else {}
            ),
        }

        exact.process_market(state, env_obj)

        new_events = exact.all_market_events[before_n:]
        rows[t]["market_events"] = successful_event_signature(new_events)
        rows[t]["post_market"] = {
            "public_market": public_market_snapshot(market),
            "self_cash": float(obs0.farms[seat]["money"]),
            "opponent_cash": float(obs0.farms[opp]["money"]),
            "self_shed": compact_map(self_private.get("shed", {}) or {}),
            "opponent_shed": compact_map(opp_private.get("shed", {}) or {}),
        }

    kg._process_market = observed_market
    try:
        players = [basecfg.OPPONENT, basecfg.OPPONENT]
        players[seat] = observed_agent
        env.run(players)
        rewards = [float(x.reward) for x in env.state]
        steps = horizon.extract_replay(env)
    finally:
        kg._process_market = original_market

    # Need the same MILK physical timeline used by earlier probes.
    physical_rows = {}
    for idx, step in enumerate(steps):
        obs = step[seat].get("observation", {}) or {}
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        player = int(obs.get("player", seat) or seat)
        farms = obs.get("farms", []) or []
        if player >= len(farms):
            continue
        physical_rows[key(day, hour)] = {
            "milk_state": phys.farm_milk_state(
                farms[player], obs.get("private", {}) or {}
            )
        }

    realized_milk = [
        e for e in exact.events if e["player"] == seat
    ]
    realized_by_turn = defaultdict(list)
    for e in realized_milk:
        realized_by_turn[key(e["day"], e["hour"])].append(e)

    return {
        "terminal": {
            "self": rewards[seat],
            "opponent": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat],
        },
        "rows": rows,
        "physical_rows": physical_rows,
        "pre_market": {
            t: r["pre_market"]
            for t, r in rows.items()
            if "pre_market" in r
        },
        "realized_milk_sell_by_turn": dict(realized_by_turn),
    }


def first_realized_milk_sell_difference(a: Dict[str, Any], b: Dict[str, Any]):
    turns = sorted(
        set(a["realized_milk_sell_by_turn"]) | set(b["realized_milk_sell_by_turn"]),
        key=tp,
    )
    for t in turns:
        aa = a["realized_milk_sell_by_turn"].get(t, [])
        bb = b["realized_milk_sell_by_turn"].get(t, [])
        sa = [
            (
                float(x["cash_delta"]),
                float(x["unit_price"]),
                int(x["market_inventory_before"]),
            )
            for x in aa
        ]
        sb = [
            (
                float(x["cash_delta"]),
                float(x["unit_price"]),
                int(x["market_inventory_before"]),
            )
            for x in bb
        ]
        if sa != sb:
            return t
    return None


def physical_decision(a: Dict[str, Any], b: Dict[str, Any], sell_t: str):
    common = sorted(
        set(a["physical_rows"]) & set(b["physical_rows"]),
        key=tp,
    )
    last_equal = None
    for t in common:
        if tp(t) > tp(sell_t):
            break
        am = a["physical_rows"][t]["milk_state"]
        bm = b["physical_rows"][t]["milk_state"]
        if phys.physical_equal(am, bm):
            last_equal = t
        else:
            return {
                "last_equal": last_equal,
                "first_physical_difference": t,
            }
    return None


def current_and_history_match(a: Dict[str, Any], b: Dict[str, Any], decision_t: str):
    ar = a["pre_market"][decision_t]
    br = b["pre_market"][decision_t]
    cur_a = {
        "price": float(ar["public_market"]["prices"]["MILK"]),
        "inventory": int(ar["public_market"]["inventory"]["MILK"]),
    }
    cur_b = {
        "price": float(br["public_market"]["prices"]["MILK"]),
        "inventory": int(br["public_market"]["inventory"]["MILK"]),
    }
    current_equal = cur_a == cur_b

    turns = rawhist.previous_common_turns(
        a["pre_market"], b["pre_market"], decision_t, HISTORY_WINDOW
    )

    def s(arm):
        return [
            {
                "timestamp": t,
                "price": float(
                    arm["pre_market"][t]["public_market"]["prices"]["MILK"]
                ),
                "inventory": int(
                    arm["pre_market"][t]["public_market"]["inventory"]["MILK"]
                ),
            }
            for t in turns
        ]

    ah = s(a)
    bh = s(b)
    return {
        "current_equal": current_equal,
        "history_equal": ah == bh,
        "current_A": cur_a,
        "current_B": cur_b,
        "history_A": ah,
        "history_B": bh,
    }


def diff_categories(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    diffs = {}

    apre = a.get("pre_market", {})
    bpre = b.get("pre_market", {})
    apost = a.get("post_market", {})
    bpost = b.get("post_market", {})

    if apre.get("self_sell_ready_milk") != bpre.get("self_sell_ready_milk"):
        diffs["SELF_SELL_READY_MILK"] = {
            "A": apre.get("self_sell_ready_milk"),
            "B": bpre.get("self_sell_ready_milk"),
        }

    if apre.get("self_shed") != bpre.get("self_shed"):
        diffs["SELF_SHED"] = {
            "A": apre.get("self_shed"),
            "B": bpre.get("self_shed"),
        }

    if apre.get("self_non_milk_carry") != bpre.get("self_non_milk_carry"):
        diffs["SELF_NON_MILK_CARRY"] = {
            "A": apre.get("self_non_milk_carry"),
            "B": bpre.get("self_non_milk_carry"),
        }

    if apre.get("public_market") != bpre.get("public_market"):
        diffs["PUBLIC_MARKET_BEFORE"] = {
            "A": apre.get("public_market"),
            "B": bpre.get("public_market"),
        }

    if apre.get("opponent_action") != bpre.get("opponent_action"):
        diffs["OPPONENT_ACTION"] = {
            "A": apre.get("opponent_action"),
            "B": bpre.get("opponent_action"),
        }

    if a.get("market_events", []) != b.get("market_events", []):
        diffs["MARKET_EXECUTION"] = {
            "A": a.get("market_events", []),
            "B": b.get("market_events", []),
        }

    if apost.get("public_market") != bpost.get("public_market"):
        diffs["PUBLIC_MARKET_AFTER"] = {
            "A": apost.get("public_market"),
            "B": bpost.get("public_market"),
        }

    if apost.get("self_cash") != bpost.get("self_cash"):
        diffs["SELF_CASH_AFTER"] = {
            "A": apost.get("self_cash"),
            "B": bpost.get("self_cash"),
        }

    if apost.get("opponent_cash") != bpost.get("opponent_cash"):
        diffs["OPPONENT_CASH_AFTER"] = {
            "A": apost.get("opponent_cash"),
            "B": bpost.get("opponent_cash"),
        }

    return diffs


def main():
    cases = []

    for seed, seat in CASES:
        a = play(seed, seat, "A")
        b = play(seed, seat, "B")
        delta_self = b["terminal"]["self"] - a["terminal"]["self"]

        sell_t = first_realized_milk_sell_difference(a, b)
        if sell_t is None:
            cases.append({
                "seed": seed,
                "status": "NO_MILK_SELL_DIFFERENCE",
                "delta_terminal_self_B_minus_A": delta_self,
            })
            continue

        pd = physical_decision(a, b, sell_t)
        if not pd or not pd["last_equal"]:
            cases.append({
                "seed": seed,
                "status": "NO_COMPACT_PHYSICAL_PRECURSOR",
                "delta_terminal_self_B_minus_A": delta_self,
                "first_milk_sell_difference": sell_t,
            })
            continue

        match = current_and_history_match(a, b, pd["last_equal"])
        if not (match["current_equal"] and match["history_equal"]):
            cases.append({
                "seed": seed,
                "status": "NOT_MATCHED_CURRENT_AND_HISTORY",
                "delta_terminal_self_B_minus_A": delta_self,
                "decision_timestamp": pd["last_equal"],
                "first_physical_difference": pd["first_physical_difference"],
                "first_milk_sell_difference": sell_t,
                "match": match,
            })
            continue

        # Start strictly after the known compact MILK physical difference.
        start_pair = tp(pd["first_physical_difference"])
        end_pair = tp(sell_t)
        turns = sorted(
            [
                t for t in set(a["rows"]) & set(b["rows"])
                if tp(t) > start_pair and tp(t) <= end_pair
            ],
            key=tp,
        )

        first = None
        for t in turns:
            d = diff_categories(a["rows"][t], b["rows"][t])
            if d:
                first = {
                    "timestamp": t,
                    "turns_after_first_physical_difference": (
                        (tp(t)[0] - start_pair[0]) * 24
                        + (tp(t)[1] - start_pair[1])
                    ),
                    "categories": d,
                }
                break

        cases.append({
            "seed": seed,
            "seat": seat,
            "status": "OBSERVED",
            "delta_terminal_self_B_minus_A": delta_self,
            "decision_timestamp": pd["last_equal"],
            "first_physical_difference": pd["first_physical_difference"],
            "first_milk_sell_difference": sell_t,
            "current_and_history_match": match,
            "first_downstream_world_difference": first,
        })

    observed = [c for c in cases if c.get("status") == "OBSERVED"]
    category_counts = defaultdict(int)
    for c in observed:
        first = c["first_downstream_world_difference"]
        if not first:
            category_counts["NO_DOWNSTREAM_DIFF_BEFORE_MILK_SELL"] += 1
            continue
        for cat in first["categories"]:
            category_counts[cat] += 1

    result = {
        "schema": "kaggriculture.post-decision-world-first-difference.fresh10.result.v0",
        "summary": {
            "matched_current_and_history_cases": len(observed),
            "first_difference_category_counts": dict(sorted(category_counts.items())),
            "by_seed": {
                str(c["seed"]): {
                    "delta_terminal_self_B_minus_A": c[
                        "delta_terminal_self_B_minus_A"
                    ],
                    "decision_timestamp": c["decision_timestamp"],
                    "first_physical_difference": c["first_physical_difference"],
                    "first_milk_sell_difference": c["first_milk_sell_difference"],
                    "first_downstream_world_difference": c[
                        "first_downstream_world_difference"
                    ],
                }
                for c in observed
            },
        },
        "cases": cases,
        "boundary": [
            "Primary set requires exact-equal current MILK price/inventory and exact-equal previous-6-turn raw MILK price/inventory history.",
            "Scan starts strictly after the already-known compact MILK physical stage divergence.",
            "Known self MILK COW/Carry stage difference and self unit-action difference are excluded as candidate downstream events.",
            "All difference categories at the earliest differing timestamp are retained; no category priority is imposed.",
            "The first downstream difference is chronological evidence only, not proof that it causes later MILK Cash or terminal differences.",
        ],
    }

    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "POST_DECISION_WORLD_FIRST_DIFFERENCE "
        + json.dumps(
            {
                "summary": result["summary"],
                "cases": [
                    {
                        "seed": c["seed"],
                        "status": c["status"],
                        "first_downstream_world_difference": c.get(
                            "first_downstream_world_difference"
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
