#!/usr/bin/env python3
"""Difference Propagation Observer v0.

Reads the existing fresh30 paired traces through the existing boundary observer.
This observer does NOT infer reachability from action divergence.
Reachability remains unknown unless an explicit domain witness is available.

Goal:
Difference -> Persist -> Reachability Changed -> Transformation Diverged -> Next Difference

Terminal is attached only after the propagation record is built.
"""

from __future__ import annotations

import json
from collections import Counter

import observe_bundle_flow_gate_boundary_v1 as src


STATE_KEYS = (
    "self_money",
    "opp_money",
    "self_hands",
    "self_land",
    "self_cows",
    "opp_hands",
    "opp_land",
    "opp_cows",
)


def num_delta(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = float(b) - float(a)
        return 0.0 if abs(d) < 1e-9 else d
    return None if a == b else [a, b]


def dict_delta(a, b):
    out = {}
    for key in sorted(set(a or {}) | set(b or {})):
        d = num_delta((a or {}).get(key), (b or {}).get(key))
        if d not in (None, 0, 0.0):
            out[key] = d
    return out


def state_difference(b, c):
    out = {}
    for key in STATE_KEYS:
        d = num_delta(b.get(key), c.get(key))
        if d not in (None, 0, 0.0):
            out[key] = d

    stock = dict_delta(b.get("stock", {}), c.get("stock", {}))
    prices = dict_delta(b.get("market_prices", {}), c.get("market_prices", {}))
    inventory = dict_delta(b.get("market_inventory", {}), c.get("market_inventory", {}))
    if stock:
        out["stock"] = stock
    if prices:
        out["market_prices"] = prices
    if inventory:
        out["market_inventory"] = inventory
    return out


def domains(diff):
    ds = []
    if "self_money" in diff:
        ds.append("self_money")
    if "stock" in diff:
        ds.append("stock")
    if any(k in diff for k in ("self_hands", "self_land", "self_cows")):
        ds.append("self_capacity")
    if any(k in diff for k in ("market_prices", "market_inventory")):
        ds.append("market")
    if any(k in diff for k in ("opp_money", "opp_hands", "opp_land", "opp_cows")):
        ds.append("opponent")
    return ds


def first_state_difference(bt, ct):
    for i in range(min(len(bt), len(ct))):
        diff = state_difference(bt[i], ct[i])
        if diff:
            return i, diff
    return None, {}


def same_domain_persists(diff, next_diff):
    if not diff:
        return False
    current = set(domains(diff))
    later = set(domains(next_diff))
    return bool(current & later)


def explicit_reachability_witness(bt, ct, i, diff):
    """Use only already-observed domain boundaries; otherwise unknown.

    Current explicit witness:
    - if self_cows differs and the next action bundles differ in a WHEAT market
      replenishment action, we can say the known cow/feed/replenishment branch
      reached a different available/used replenishment path.
    This is deliberately narrow.
    """
    if i is None or i + 1 >= min(len(bt), len(ct)):
        return {"changed": "unknown", "witness": None}

    if "self_cows" in diff:
        ba = bt[i + 1].get("action")
        ca = ct[i + 1].get("action")

        def wheat_market(action):
            if not isinstance(action, dict):
                return []
            out = []
            for a in action.get("market", []) or []:
                if isinstance(a, (list, tuple)) and len(a) >= 2 and a[1] == "WHEAT":
                    out.append(list(a))
            return out

        bw = wheat_market(ba)
        cw = wheat_market(ca)
        if bw != cw:
            return {
                "changed": "yes",
                "witness": {
                    "kind": "known_cow_to_wheat_replenishment_branch",
                    "baseline_wheat_market": bw,
                    "control_wheat_market": cw,
                },
            }

    return {"changed": "unknown", "witness": None}


def analyze(seed, seat):
    baseline = src.play(seed, seat, False)
    control = src.play(seed, seat, True)
    bt, ct = baseline["trace"], control["trace"]

    i, diff = first_state_difference(bt, ct)
    if i is None:
        propagation = {
            "difference_turn": None,
            "difference": {},
            "persist": "no",
            "reachability_changed": "unknown",
            "reachability_witness": None,
            "transformation_diverged": "no",
            "transformation_turn": None,
            "next_difference": {},
            "status": "no_observed_state_difference",
        }
    else:
        next_diff = state_difference(bt[i + 1], ct[i + 1]) if i + 1 < min(len(bt), len(ct)) else {}
        persist = same_domain_persists(diff, next_diff)
        reach = explicit_reachability_witness(bt, ct, i, diff)

        transformation_turn = None
        for j in range(i, min(len(bt), len(ct))):
            if bt[j].get("action") != ct[j].get("action"):
                transformation_turn = j
                break

        transformation_diverged = transformation_turn is not None

        post_index = None
        post_diff = {}
        if transformation_turn is not None:
            for j in range(transformation_turn + 1, min(len(bt), len(ct))):
                candidate = state_difference(bt[j], ct[j])
                if candidate:
                    post_index = j
                    post_diff = candidate
                    break

        if not persist:
            status = "stop_at_persist"
        elif reach["changed"] == "no":
            status = "stop_at_reachability"
        elif transformation_diverged and post_diff:
            status = "continue_to_next_difference"
        elif transformation_diverged:
            status = "transformation_diverged_next_difference_unobserved"
        else:
            status = "reachability_or_transformation_unresolved"

        propagation = {
            "difference_turn": i,
            "difference_day": ct[i].get("day"),
            "difference": diff,
            "difference_domains": domains(diff),
            "persist": "yes" if persist else "no",
            "next_turn_difference": next_diff,
            "reachability_changed": reach["changed"],
            "reachability_witness": reach["witness"],
            "transformation_diverged": "yes" if transformation_diverged else "no",
            "transformation_turn": transformation_turn,
            "next_difference_turn": post_index,
            "next_difference": post_diff,
            "next_difference_domains": domains(post_diff),
            "status": status,
        }

    terminal = {
        "self_diff": control["terminal_self"] - baseline["terminal_self"],
        "opp_diff": control["terminal_opp"] - baseline["terminal_opp"],
        "margin_diff": control["terminal_margin"] - baseline["terminal_margin"],
    }
    terminal["class"] = (
        "improved" if terminal["self_diff"] > 0
        else "worsened" if terminal["self_diff"] < 0
        else "equal"
    )

    return {
        "seed": seed,
        "seat": seat,
        "propagation": propagation,
        "terminal": terminal,
    }


def summarize(rows):
    return {
        "case_count": len(rows),
        "status_counts": dict(Counter(r["propagation"]["status"] for r in rows)),
        "first_difference_domains": dict(Counter(
            "+".join(r["propagation"].get("difference_domains", [])) or "none"
            for r in rows
        )),
        "reachability": dict(Counter(r["propagation"].get("reachability_changed", "unknown") for r in rows)),
        "transformation_diverged": dict(Counter(r["propagation"].get("transformation_diverged", "unknown") for r in rows)),
        "terminal_class": dict(Counter(r["terminal"]["class"] for r in rows)),
    }


def main():
    rows = [analyze(seed, seat) for seed, seat in src.CASES]
    out = {
        "schema": "kaggriculture.difference-propagation-observer.v0",
        "observation_columns": [
            "Difference",
            "Persist",
            "Reachability Changed",
            "Transformation Diverged",
            "Next Difference",
        ],
        "terminal_postponed": True,
        "reachability_policy": "do not infer from action difference; unknown unless explicit witness exists",
        "policy_mutated": False,
        "cases": rows,
        "summary": summarize(rows),
        "boundary": [
            "This observer standardizes propagation evidence; it does not identify causes or winners.",
            "Terminal is attached after propagation extraction and is not used to define the path.",
            "Unknown reachability stays unknown.",
        ],
    }
    with open("difference_propagation_observer_v0.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("DIFFERENCE_PROPAGATION_OBSERVER_V0 " + json.dumps(out["summary"], separators=(",", ":")))
    compact = []
    for r in rows:
        p = r["propagation"]
        compact.append({
            "seed": r["seed"],
            "seat": r["seat"],
            "difference_turn": p.get("difference_turn"),
            "difference_domains": p.get("difference_domains", []),
            "persist": p.get("persist"),
            "reachability": p.get("reachability_changed"),
            "transformation_turn": p.get("transformation_turn"),
            "next_difference_turn": p.get("next_difference_turn"),
            "next_difference_domains": p.get("next_difference_domains", []),
            "status": p.get("status"),
            "terminal_class": r["terminal"]["class"],
        })
    print("DIFFERENCE_PROPAGATION_ROWS " + json.dumps(compact, separators=(",", ":")))


if __name__ == "__main__":
    main()
