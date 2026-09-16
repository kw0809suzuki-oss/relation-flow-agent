"""Production Agent v10: external body-scale layer over frozen v6.

Goal: grow the body without changing v6 decision logic.
One external scale unit only:
- target 3 land quadrants
- target 11 hands
- target 13 total animals (COW purchases)

No Bundle / Relation / Flow signal is read for runtime control.
The scale layer only appends affordable market capacity orders to v6's action.
"""

import copy

import production_agent_v6_bridge1 as base
import strong_origin_g5 as g5

TARGET_LAND = 3
TARGET_HANDS = 11
TARGET_ANIMALS = 13
MIN_RESERVE = 350
COW_COST = 400.0

_STATS = {
    "turns": 0,
    "scale_land_orders": 0,
    "scale_hire_orders": 0,
    "scale_animal_orders": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for k in _STATS:
        _STATS[k] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v10_external_scale"] = {
        **_STATS,
        "target_land": TARGET_LAND,
        "target_hands": TARGET_HANDS,
        "target_animals": TARGET_ANIMALS,
        "min_reserve": MIN_RESERVE,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def _animal_count(me, private):
    total = 0
    for row in me.get("tiles", []) or []:
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal"):
                total += 1
    shed = private.get("shed", {}) or {}
    total += sum(int(shed.get(k, 0) or 0) for k in ("COW", "SHEEP", "CHICKEN"))
    for inv in private.get("inventories", []) or []:
        total += sum(int(inv.get(k, 0) or 0) for k in ("COW", "SHEEP", "CHICKEN"))
    return total


def _estimate_base_spend(action, me, obs):
    prices = obs.get("market", {}).get("prices", {}) or {}
    spend = 0.0
    quadrants = len(me.get("unlocked_quadrants", []) or [])
    hires_today = int(me.get("hires_today", 0) or 0)
    extra_hires = 0
    for o in action.get("market", []) or []:
        if not o:
            continue
        kind = o[0]
        if kind == "BUY_LAND":
            spend += {1: 1000.0, 2: 2000.0, 3: 4000.0}.get(quadrants, 0.0)
            quadrants += 1
        elif kind == "HIRE":
            spend += float(g5.fib_hire_cost(hires_today + extra_hires))
            extra_hires += 1
        elif kind == "BUY_ANIMAL" and len(o) >= 3:
            unit = {"COW": 400.0, "SHEEP": 400.0, "CHICKEN": 250.0}.get(o[1], 400.0)
            spend += unit * float(o[2])
        elif kind == "BUY_SEED" and len(o) >= 3:
            spend += float(g5.SEED_COST.get(o[1], 0.0)) * float(o[2])
        elif kind == "BUY_PRODUCT" and len(o) >= 3:
            spend += float(prices.get(o[1], 25.0)) * float(o[2])
    return spend


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    player = int(obs["player"])
    me = obs["farms"][player]
    private = obs.get("private", {}) or {}
    market = list(action.get("market", []) or [])
    if len(market) >= 10:
        return action

    money = float(me.get("money", 0) or 0)
    projected = money - _estimate_base_spend(action, me, obs)

    # 1) Land: grow the body to 3 quadrants.
    quadrants = len(me.get("unlocked_quadrants", []) or [])
    planned_land = sum(1 for o in market if o and o[0] == "BUY_LAND")
    while quadrants + planned_land < TARGET_LAND and len(market) < 10:
        q = quadrants + planned_land
        cost = {1: 1000.0, 2: 2000.0, 3: 4000.0}.get(q)
        if cost is None or projected - cost < MIN_RESERVE:
            break
        market.append(["BUY_LAND"])
        projected -= cost
        planned_land += 1
        _STATS["scale_land_orders"] += 1

    # 2) Hands: raise working capacity toward 11.
    current_hands = len(me.get("hands", []) or [])
    existing_hires = sum(1 for o in market if o and o[0] == "HIRE")
    planned_hands = current_hands + existing_hires
    next_hire_index = int(me.get("hires_today", 0) or 0) + existing_hires
    while planned_hands < TARGET_HANDS and len(market) < 10:
        cost = float(g5.fib_hire_cost(next_hire_index))
        if projected - cost < MIN_RESERVE:
            break
        market.append(["HIRE"])
        projected -= cost
        planned_hands += 1
        next_hire_index += 1
        _STATS["scale_hire_orders"] += 1

    # 3) Animals: enlarge the productive body toward 13 total animals.
    animals = _animal_count(me, private)
    planned_animals = sum(int(o[2]) for o in market if o and o[0] == "BUY_ANIMAL" and len(o) >= 3)
    while animals + planned_animals < TARGET_ANIMALS and len(market) < 10:
        if projected - COW_COST < MIN_RESERVE:
            break
        market.append(["BUY_ANIMAL", "COW", 1])
        projected -= COW_COST
        planned_animals += 1
        _STATS["scale_animal_orders"] += 1

    action["market"] = market
    return action
