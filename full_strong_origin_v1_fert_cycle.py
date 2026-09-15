"""Full v1 + one-step fertilizer reinvestment experiment.

Goal:
- keep Full Strong Origin v1 intact as the baseline body
- retain a small fertilizer reserve instead of auto-selling all of it
- dedicate at most one hand to move one fertilizer unit from shed -> plant -> FERTILIZE

This is intentionally a narrow intervention. It does not change crop targets,
livestock targets, market reading, or investment gates.
"""

import copy

import full_strong_origin_v1 as base

FERTILIZER_RESERVE = 3

_STATS = {
    "turns": 0,
    "fertilizer_sell_units_withheld": 0,
    "fertilizer_pickups": 0,
    "fertilize_actions": 0,
    "fertilizer_moves": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["fert_cycle"] = dict(_STATS)
    data["fert_cycle"]["reserve"] = FERTILIZER_RESERVE
    return data


def _adjacent_shed(x, y, board_size):
    h = board_size // 2
    return (x, y) in {(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)}


def _nearest(src, points):
    if not points:
        return None
    x, y = src
    return min(points, key=lambda p: abs(p[0] - x) + abs(p[1] - y))


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


def _fertilizer_targets(obs):
    """Return currently useful fertilizer targets without price prediction."""
    me = obs["farms"][obs["player"]]
    day = obs["day"]
    targets = []
    for y, row in enumerate(me["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                continue
            crop = tile.get("crop")
            fertilized_until = tile.get("fertilized_until_day", -1)
            if fertilized_until >= day:
                continue
            age = day - tile.get("planted_day", day)
            # Ongoing STRAWBERRY can convert fertilizer into repeated production.
            if crop == "STRAWBERRY":
                targets.append((0, x, y))
            # One-time crops only receive fertilizer when already inside the
            # watering/yield window, so the action is close to monetization.
            elif crop == "MELON" and 6 <= age <= 12:
                targets.append((1, x, y))
            elif crop == "WHEAT" and 2 <= age <= 4:
                targets.append((2, x, y))
    targets.sort()
    return [(x, y) for _, x, y in targets]


def _retain_fertilizer(market, shed_fertilizer):
    """Keep up to FERTILIZER_RESERVE units in the shed instead of selling all."""
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


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    shed = private.get("shed", {})
    inventories = list(private.get("inventories", []))
    hands = list(me.get("hands", []))
    tiles = me["tiles"]
    board_size = len(tiles)

    action["market"] = _retain_fertilizer(action.get("market", []), shed.get("FERTILIZER", 0))

    # Keep the intervention narrow: only a hired hand may become the fertilizer
    # courier. The farmer remains available to the existing Full v1 body.
    if not hands:
        return action

    targets = _fertilizer_targets(obs)
    if not targets:
        return action

    unit_index = len(hands)  # inventories: farmer=0, last hand=len(hands)
    hand_index = len(hands) - 1
    while len(inventories) <= unit_index:
        inventories.append({})
    inv = inventories[unit_index]
    pos = tuple(hands[hand_index])
    fert_carried = int(inv.get("FERTILIZER", 0))

    hand_actions = list(action.get("hands", []))
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])

    if fert_carried > 0:
        target = _nearest(pos, targets)
        if target == pos:
            hand_actions[hand_index] = ["FERTILIZE"]
            _STATS["fertilize_actions"] += 1
        else:
            hand_actions[hand_index] = _move_toward(pos, target)
            _STATS["fertilizer_moves"] += 1
        action["hands"] = hand_actions
        return action

    shed_fert = int(shed.get("FERTILIZER", 0))
    if shed_fert <= 0:
        return action

    if _adjacent_shed(pos[0], pos[1], board_size):
        hand_actions[hand_index] = ["PICKUP", "FERTILIZER", 1]
        _STATS["fertilizer_pickups"] += 1
    else:
        h = board_size // 2
        shed_points = [(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)]
        hand_actions[hand_index] = _move_toward(pos, _nearest(pos, shed_points))
        _STATS["fertilizer_moves"] += 1

    action["hands"] = hand_actions
    return action
