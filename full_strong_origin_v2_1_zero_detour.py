"""Full Strong Origin v2.1: zero-detour edge intervention over Full v1.

Design:
- preserve Full v1 as the body
- never replace productive hand actions (HARVEST/FEED/WATER/DROP/etc.)
- only consider hands whose Full v1 action is PASS or simple movement
- allow fertilizer intervention only when the relevant interaction is at the
  current tile or within one Manhattan step
- keep livestock feed pressure as a hard guard
- retain at most one fertilizer unit, and only when a near-shed hand can
  actually start the edge flow

This tests whether a weak, path-adjacent intervention can fire without creating
long fertilizer-specific travel or dedicated labor.
"""

import copy

import full_strong_origin_v1 as base

FERTILIZER_RESERVE = 1
ALLOWED_BASE_ACTIONS = {"PASS", "NORTH", "SOUTH", "EAST", "WEST"}

_STATS = {
    "turns": 0,
    "feed_pressure_turns": 0,
    "eligible_edge_turns": 0,
    "fertilizer_sell_units_withheld": 0,
    "fertilizer_pickups": 0,
    "fertilize_actions": 0,
    "fertilizer_moves": 0,
    "skipped_no_edge": 0,
    "skipped_feed_pressure": 0,
    "skipped_productive_action": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["whole_v2_1"] = dict(_STATS)
    data["whole_v2_1"]["fertilizer_reserve"] = FERTILIZER_RESERVE
    data["whole_v2_1"]["composition"] = "feed-first + zero-detour edge fertilizer intervention"
    return data


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _nearest(src, points):
    if not points:
        return None
    return min(points, key=lambda p: _distance(src, p))


def _move_toward(src, dst):
    x, y = src
    tx, ty = dst
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _shed_points(board_size):
    h = board_size // 2
    return [(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)]


def _adjacent_shed(pos, board_size):
    return pos in set(_shed_points(board_size))


def _fertilizer_targets(obs):
    me = obs["farms"][obs["player"]]
    day = obs["day"]
    targets = []
    for y, row in enumerate(me["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                continue
            if tile.get("fertilized_until_day", -1) >= day:
                continue
            crop = tile.get("crop")
            age = day - tile.get("planted_day", day)
            if crop == "STRAWBERRY":
                targets.append((0, x, y))
            elif crop == "MELON" and 6 <= age <= 12:
                targets.append((1, x, y))
            elif crop == "WHEAT" and 2 <= age <= 4:
                targets.append((2, x, y))
    targets.sort()
    return [(x, y) for _, x, y in targets]


def _feed_pressure(obs):
    me = obs["farms"][obs["player"]]
    private = obs["private"]
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])
    cows_on_farm = 0
    for row in me.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and tile.get("animal") == "COW":
                cows_on_farm += 1
    carried_cows = sum(int(inv.get("COW", 0)) for inv in inventories)
    carried_wheat = sum(int(inv.get("WHEAT", 0)) for inv in inventories)
    total_cows = cows_on_farm + int(shed.get("COW", 0)) + carried_cows
    feed_stock = int(shed.get("WHEAT", 0)) + carried_wheat
    return total_cows > 0 and feed_stock < total_cows * 2


def _retain_one_fertilizer(market, shed_fertilizer):
    keep = min(FERTILIZER_RESERVE, max(0, int(shed_fertilizer)))
    out = []
    for order in market:
        if not order or order[0] != "SELL" or len(order) < 3 or order[1] != "FERTILIZER":
            out.append(order)
            continue
        original = int(order[2])
        sell = max(0, original - keep)
        withheld = original - sell
        _STATS["fertilizer_sell_units_withheld"] += withheld
        if sell > 0:
            out.append(["SELL", "FERTILIZER", sell])
    return out


def _is_light_action(action):
    return bool(action) and action[0] in ALLOWED_BASE_ACTIONS


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    shed = private.get("shed", {})
    hands = list(me.get("hands", []))
    inventories = list(private.get("inventories", []))
    board_size = len(me["tiles"])
    targets = _fertilizer_targets(obs)

    if not hands or not targets:
        _STATS["skipped_no_edge"] += 1
        return action

    if _feed_pressure(obs):
        _STATS["feed_pressure_turns"] += 1
        _STATS["skipped_feed_pressure"] += 1
        return action

    hand_actions = list(action.get("hands", []))
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])
    while len(inventories) < 1 + len(hands):
        inventories.append({})

    light = [i for i, a in enumerate(hand_actions) if _is_light_action(a)]
    _STATS["skipped_productive_action"] += len(hands) - len(light)
    if not light:
        _STATS["skipped_no_edge"] += 1
        return action

    # First priority: a hand already carrying fertilizer may act only if a
    # useful target is on the current tile or one step away.
    carrying = []
    for i in light:
        if int(inventories[i + 1].get("FERTILIZER", 0)) <= 0:
            continue
        pos = tuple(hands[i])
        target = _nearest(pos, targets)
        if target is not None and _distance(pos, target) <= 1:
            carrying.append((i, pos, target))

    if carrying:
        hand_index, pos, target = min(carrying, key=lambda row: _distance(row[1], row[2]))
        _STATS["eligible_edge_turns"] += 1
        if pos == target:
            hand_actions[hand_index] = ["FERTILIZE"]
            _STATS["fertilize_actions"] += 1
        else:
            hand_actions[hand_index] = _move_toward(pos, target)
            _STATS["fertilizer_moves"] += 1
        action["hands"] = hand_actions
        return action

    # Start a fertilizer edge-flow only when a light-action hand is already at
    # the shed edge AND a useful crop target is within one step of that hand.
    # This prevents creating fertilizer-specific cross-board travel.
    if int(shed.get("FERTILIZER", 0)) <= 0:
        _STATS["skipped_no_edge"] += 1
        return action

    starters = []
    for i in light:
        pos = tuple(hands[i])
        if not _adjacent_shed(pos, board_size):
            continue
        target = _nearest(pos, targets)
        if target is not None and _distance(pos, target) <= 1:
            starters.append((i, pos, target))

    if not starters:
        _STATS["skipped_no_edge"] += 1
        return action

    hand_index, _, _ = starters[0]
    _STATS["eligible_edge_turns"] += 1
    action["market"] = _retain_one_fertilizer(action.get("market", []), shed.get("FERTILIZER", 0))
    hand_actions[hand_index] = ["PICKUP", "FERTILIZER", 1]
    _STATS["fertilizer_pickups"] += 1
    action["hands"] = hand_actions
    return action
