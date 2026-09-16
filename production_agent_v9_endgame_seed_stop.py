"""Production Agent v9: endgame seed-stop candidate.

Single front-side change over v6:
- from day 24 onward, remove BUY_SEED market orders only
- keep hires, livestock inputs, SELL, farmer/hands work, and all other v6 behavior

Bundle / Relation / Flow remain observation-only.
"""

import copy
import production_agent_v6_bridge1 as base

SEED_STOP_DAY = 24

_STATS = {"turns": 0, "seed_stop_turns": 0, "seed_orders_removed": 0}


def reset_telemetry():
    base.reset_telemetry()
    for k in _STATS:
        _STATS[k] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v9_endgame_seed_stop"] = {
        **_STATS,
        "seed_stop_day": SEED_STOP_DAY,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1
    day = int(obs.get("day", 0))
    if day < SEED_STOP_DAY:
        return action

    _STATS["seed_stop_turns"] += 1
    market = []
    for order in action.get("market", []) or []:
        if order and order[0] == "BUY_SEED":
            _STATS["seed_orders_removed"] += 1
            continue
        market.append(order)
    action["market"] = market
    return action
