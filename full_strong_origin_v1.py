"""Full Strong Origin v1: broad whole-agent candidate before pruning.

Composition strategy:
- keep the current G5 coordinated Strong Origin body
- keep the observable land/hire ROI gate
- reattach the historical G8 livestock revenue loop as a whole subsystem
- deliberately allow a fat first version so later runs can prune weak branches

This is not a claim that each subsystem is independently optimal. The purpose is
to restore a complete economic loop first, then observe and cut.
"""

import g8_agent as livestock
import strong_origin_g5_roi as base

# Broader whole-agent targets. These are intentionally not treated as final
# optima; they give the livestock loop enough body to be judged as a system.
COW_TARGETS = ((5, 2), (9, 4), (14, 6), (20, 8))
FEED_CARRY = 4

_STATS = {
    "turns": 0,
    "buy_animal_orders": 0,
    "buy_wheat_orders": 0,
    "sell_orders": 0,
    "work_actions": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["full_v1"] = dict(_STATS)
    data["full_v1"]["cow_targets"] = [list(x) for x in COW_TARGETS]
    data["full_v1"]["feed_carry"] = FEED_CARRY
    return data


def agent(obs):
    previous_base = livestock.g7
    previous_targets = livestock.COW_TARGETS
    previous_feed = livestock.FEED_CARRY
    livestock.g7 = base
    livestock.COW_TARGETS = COW_TARGETS
    livestock.FEED_CARRY = FEED_CARRY
    try:
        action = livestock.agent(obs)
    finally:
        livestock.g7 = previous_base
        livestock.COW_TARGETS = previous_targets
        livestock.FEED_CARRY = previous_feed

    _STATS["turns"] += 1
    for order in action.get("market", []):
        if not order:
            continue
        if order[0] == "BUY_ANIMAL":
            _STATS["buy_animal_orders"] += 1
        elif order[0] == "BUY_PRODUCT" and len(order) > 1 and order[1] == "WHEAT":
            _STATS["buy_wheat_orders"] += 1
        elif order[0] == "SELL":
            _STATS["sell_orders"] += 1
    for unit_action in [action.get("farmer", ["PASS"]), *action.get("hands", [])]:
        if unit_action and unit_action[0] in {
            "BUILD_PASTURE", "PLACE", "PICKUP", "DROP", "FEED", "CARE",
            "HARVEST", "COLLECT_FERTILIZER", "DIG", "PLANT", "WATER"
        }:
            _STATS["work_actions"] += 1
    return action
