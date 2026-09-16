"""Production Agent v4: top-practice midgame scale bridge.

Single functional unit over frozen v3:
- keep v3 production body unchanged
- during midgame, allow one more land step toward 3 quadrants
- raise hands toward 10 so the larger surface has matching parallel capacity
- leave crop/livestock/task scheduling to the existing body

No Bundle / Relation / Flow signal is read for runtime control.
"""

import copy

import production_agent_v3_expansion_bridge as base
import strong_origin_g5 as g5

SCALE_DAYS = tuple(range(7, 15))
TARGET_HANDS = 10
TARGET_QUADRANTS = 3
MIN_RESERVE = 500

_STATS = {
    "turns": 0,
    "scale_turns": 0,
    "extra_land_orders": 0,
    "extra_hire_orders": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for k in _STATS:
        _STATS[k] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v4_top_practice_scale"] = {
        **_STATS,
        "scale_days": list(SCALE_DAYS),
        "target_hands": TARGET_HANDS,
        "target_quadrants": TARGET_QUADRANTS,
        "min_reserve": MIN_RESERVE,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def _market_spend_estimate(action):
    spend = 0.0
    for o in action.get("market", []) or []:
        if not o:
            continue
        if o[0] in ("HIRE", "BUY_LAND"):
            continue
        if o[0] == "BUY_SEED" and len(o) >= 3:
            spend += float(g5.SEED_COST.get(o[1], 0)) * float(o[2])
        elif o[0] == "BUY_PRODUCT" and len(o) >= 3 and o[1] == "WHEAT":
            spend += 25.0 * float(o[2])
        elif o[0] == "BUY_ANIMAL" and len(o) >= 3:
            nominal = {"COW": 500.0, "SHEEP": 400.0, "CHICKEN": 250.0}.get(o[1], 500.0)
            spend += nominal * float(o[2])
    return spend


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    day = int(obs.get("day", 0))
    if day not in SCALE_DAYS:
        return action

    _STATS["scale_turns"] += 1
    me = obs["farms"][int(obs["player"])]
    market = list(action.get("market", []) or [])
    projected = float(me.get("money", 0)) - _market_spend_estimate(action)

    quadrants = len(me.get("unlocked_quadrants", []) or [])
    existing_land = sum(1 for o in market if o and o[0] == "BUY_LAND")
    projected_quadrants = quadrants + existing_land

    if projected_quadrants < TARGET_QUADRANTS and len(market) < 10:
        land_cost = {1: 1000.0, 2: 2000.0, 3: 4000.0}.get(projected_quadrants)
        if land_cost is not None and projected - land_cost >= MIN_RESERVE:
            market.append(["BUY_LAND"])
            projected -= land_cost
            projected_quadrants += 1
            _STATS["extra_land_orders"] += 1

    current_hands = len(me.get("hands", []) or [])
    hires_today = int(me.get("hires_today", 0))
    existing_hires = sum(1 for o in market if o and o[0] == "HIRE")
    planned_hands = current_hands + existing_hires
    next_hire_index = hires_today + existing_hires

    while planned_hands < TARGET_HANDS and len(market) < 10:
        cost = float(g5.fib_hire_cost(next_hire_index))
        if projected - cost < MIN_RESERVE:
            break
        market.append(["HIRE"])
        projected -= cost
        planned_hands += 1
        next_hire_index += 1
        _STATS["extra_hire_orders"] += 1

    action["market"] = market
    return action
