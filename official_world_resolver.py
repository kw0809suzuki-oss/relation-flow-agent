"""Official World Resolver v0.

Uses Kaggle's installed kaggriculture implementation as the only authority for
deterministic world semantics. It does not invent strategy and does not predict
opponent actions.

Flow:
raw observation -> self candidate action -> official deterministic unit
resolution -> resolved self-side facts/action -> real Battle.
"""

import copy

from kaggle_environments.envs.kaggriculture import kaggriculture as official


def _unit_actions(action):
    farmer = action.get("farmer", ["PASS"]) if isinstance(action, dict) else ["PASS"]
    hands = action.get("hands", []) if isinstance(action, dict) else []
    if not isinstance(hands, list):
        hands = []
    return [farmer, *hands]


def resolve_self_candidate(obs, action):
    """Resolve only deterministic self-side semantics known before opponent action.

    Uses the official implementation for unit actions, including:
    - atomic PLANT blocking
    - movement / tile legality
    - DROP / PICKUP / PLACE shed semantics
    - PLANT / WATER / HARVEST / FEED / CARE / FERTILIZE / DIG / BUILD

    Market interaction with the opponent is not simulated.
    """
    player = int(obs["player"])
    farm = copy.deepcopy(obs["farms"][player])
    private = copy.deepcopy(obs["private"])
    board_size = len(farm["tiles"])
    day = int(obs.get("day", 0))
    turns_per_day = 24
    shed_capacity = 100

    candidate = copy.deepcopy(action if isinstance(action, dict) else {})
    farmer_action = candidate.get("farmer", ["PASS"])
    hands_actions = candidate.get("hands", [])
    if not isinstance(hands_actions, list):
        hands_actions = []

    # Exact official atomic PLANT validation.
    unit_actions = [farmer_action, *hands_actions]
    plant_demand = {}
    for a in unit_actions:
        if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT":
            plant_demand[a[1]] = plant_demand.get(a[1], 0) + 1
    seeds = private.get("seeds", {})
    blocked = {crop for crop, n in plant_demand.items() if n > seeds.get(crop, 0)}

    def allowed(a):
        if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT" and a[1] in blocked:
            return ["PASS"]
        return a

    resolved_farmer = allowed(farmer_action)
    resolved_hands = [allowed(a) for a in hands_actions]

    official._apply_unit_action(
        farm, private, 0, resolved_farmer,
        board_size, day, turns_per_day, shed_capacity,
    )
    for idx, hand_action in enumerate(resolved_hands, start=1):
        official._apply_unit_action(
            farm, private, idx, hand_action,
            board_size, day, turns_per_day, shed_capacity,
        )

    resolved_action = copy.deepcopy(candidate)
    resolved_action["farmer"] = resolved_farmer
    resolved_action["hands"] = resolved_hands

    return {
        "resolved_action": resolved_action,
        "post_unit_farm": farm,
        "post_unit_private": private,
        "blocked_plant_crops": sorted(blocked),
        "shed_capacity": shed_capacity,
    }


def reconcile_market_with_resolved_state(obs, action, resolved):
    """Apply only deterministic self-side constraints to market orders.

    This does not predict prices or opponent actions. It only removes quantities
    that are impossible given the official post-unit shed/capacity state.
    """
    out = copy.deepcopy(action)
    orders = list(out.get("market", []) if isinstance(out, dict) else [])
    private = copy.deepcopy(resolved["post_unit_private"])
    shed = private.get("shed", {})
    capacity = int(resolved["shed_capacity"])

    fixed = []
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = order[0]

        if op == "SELL" and len(order) >= 3:
            item = order[1]
            try:
                requested = max(0, int(order[2]))
            except (TypeError, ValueError):
                continue
            executable = min(requested, max(0, int(shed.get(item, 0))))
            if executable > 0:
                fixed.append(["SELL", item, executable])
                shed[item] = shed.get(item, 0) - executable
            continue

        if op in ("BUY_PRODUCT", "BUY_ANIMAL") and len(order) >= 3:
            try:
                requested = max(0, int(order[2]))
            except (TypeError, ValueError):
                continue
            room = max(0, capacity - sum(shed.values()))
            executable = min(requested, room)
            if executable > 0:
                fixed.append([op, order[1], executable])
                shed[order[1]] = shed.get(order[1], 0) + executable
            continue

        # HIRE / BUY_LAND / BUY_SEED remain untouched here because cash and
        # shared-market interaction can depend on preceding orders/opponent.
        fixed.append(order)

    out["market"] = fixed
    return out


def resolve_action(obs, action):
    resolved = resolve_self_candidate(obs, action)
    return reconcile_market_with_resolved_state(obs, resolved["resolved_action"], resolved)
