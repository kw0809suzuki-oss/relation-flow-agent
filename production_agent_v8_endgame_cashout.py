"""Production Agent v8: endgame cash-out gate over v6 Bridge1.

Single front-side game-rule change:
- keep v6 production / bridge behavior unchanged
- from Day 24 onward, keep SELL orders but stop new market investment
- leave farmer / hand work unchanged so existing harvest / drop / sale flow can finish

Bundle / Relation / Flow remain observation-only.
"""

import copy

import production_agent_v6_bridge1 as base

ENDGAME_DAY = 24

_STATS = {
    "turns": 0,
    "endgame_turns": 0,
    "market_orders_removed": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v8_endgame_cashout"] = {
        **_STATS,
        "endgame_day": ENDGAME_DAY,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    day = int(obs.get("day", 0))
    if day < ENDGAME_DAY:
        return action

    _STATS["endgame_turns"] += 1
    market = list(action.get("market", []) or [])
    keep = [order for order in market if order and order[0] == "SELL"]
    _STATS["market_orders_removed"] += len(market) - len(keep)
    action["market"] = keep
    return action
