"""Production Agent v2: front-side capacity bridge.

Game-design change only:
- around day 7, open one additional land quadrant when affordable
- raise hired hands toward a bounded production-capacity target
- leave the existing G5/G8 task scheduler unchanged, so added capacity flows
  into the already-established production loop

Bundle / Relation / Flow are not read and never control actions.
"""

import copy

import production_agent_v1 as base
import strong_origin_g5 as g5

BRIDGE_DAYS = (7, 8)
TARGET_HANDS = 7
MIN_RESERVE = 500

_STATS = {
    "turns": 0,
    "bridge_turns": 0,
    "bridge_land_orders": 0,
    "bridge_hire_orders": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for k in _STATS:
        _STATS[k] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v2_capacity_bridge"] = {
        **_STATS,
        "bridge_days": list(BRIDGE_DAYS),
        "target_hands": TARGET_HANDS,
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
        if o[0] == "HIRE":
            # Existing hire cost is accounted approximately below via hires_today.
            continue
        if o[0] == "BUY_LAND":
            # Actual land cost depends on current quadrant count; handled in agent().
            continue
        if o[0] == "BUY_SEED" and len(o) >= 3:
            spend += float(g5.SEED_COST.get(o[1], 0)) * float(o[2])
        elif o[0] == "BUY_PRODUCT" and len(o) >= 3:
            # Only WHEAT is relevant to the current production body; keep a
            # conservative nominal estimate rather than reading future state.
            if o[1] == "WHEAT":
                spend += 25.0 * float(o[2])
        elif o[0] == "BUY_ANIMAL" and len(o) >= 3:
            # Conservative nominal envelope; exact shop pricing remains in env.
            nominal = {"COW": 500.0, "SHEEP": 400.0, "CHICKEN": 250.0}.get(o[1], 500.0)
            spend += nominal * float(o[2])
    return spend


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    day = int(obs.get("day", 0))
    if day not in BRIDGE_DAYS:
        return action

    _STATS["bridge_turns"] += 1
    me = obs["farms"][int(obs["player"])]
    market = list(action.get("market", []) or [])
    money = float(me.get("money", 0))
    projected = money - _market_spend_estimate(action)

    quadrants = len(me.get("unlocked_quadrants", []) or [])
    existing_land = sum(1 for o in market if o and o[0] == "BUY_LAND")
    land_cost = {1: 1000.0, 2: 2000.0, 3: 4000.0}.get(quadrants)

    # One bounded land step: only when the current farm is still at one quadrant
    # and no land order already exists in the base action.
    if (
        quadrants == 1
        and existing_land == 0
        and land_cost is not None
        and len(market) < 10
        and projected - land_cost >= MIN_RESERVE
    ):
        market.append(["BUY_LAND"])
        projected -= land_cost
        _STATS["bridge_land_orders"] += 1

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
        _STATS["bridge_hire_orders"] += 1

    action["market"] = market
    return action
