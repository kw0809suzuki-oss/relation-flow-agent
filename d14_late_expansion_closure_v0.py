#!/usr/bin/env python3
"""Frozen High-Leverage Candidate: Day14 coarse late-expansion suppression.

Battle candidate only; not an adopted rule.

From day >= 14, remove only these market expansion purchases from current G17:
- BUY_LAND
- BUY_SEED
- BUY_ANIMAL
- BUY_PRODUCT COW

HIRE, HARVEST, unit movement, crop logic, and all other market orders are preserved.
"""
import copy
import g17_agent as base

START_DAY = 14

_telemetry = {
    "eligible_calls": 0,
    "changed_calls": 0,
    "removed_orders": 0,
    "removed_by_op": {},
}

def reset_telemetry():
    global _telemetry
    _telemetry = {
        "eligible_calls": 0,
        "changed_calls": 0,
        "removed_orders": 0,
        "removed_by_op": {},
    }
    if hasattr(base, "reset_telemetry"):
        base.reset_telemetry()

def get_telemetry():
    return copy.deepcopy(_telemetry)

def _is_expansion(order):
    if not isinstance(order, (list, tuple)) or not order:
        return False
    op = order[0]
    if op in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(order) > 1 and order[1] == "COW"

def agent(obs):
    actions = base.agent(obs)
    if not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    if day < START_DAY:
        return actions

    _telemetry["eligible_calls"] += 1
    market = list(actions.get("market", []) or [])
    removed = [copy.deepcopy(o) for o in market if _is_expansion(o)]
    if not removed:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [o for o in market if not _is_expansion(o)]

    _telemetry["changed_calls"] += 1
    _telemetry["removed_orders"] += len(removed)
    for order in removed:
        op = order[0]
        key = "BUY_PRODUCT_COW" if op == "BUY_PRODUCT" else op
        _telemetry["removed_by_op"][key] = _telemetry["removed_by_op"].get(key, 0) + 1

    return revised
