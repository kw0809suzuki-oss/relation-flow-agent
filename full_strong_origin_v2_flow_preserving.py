"""Full Strong Origin v2: flow-preserving composition over Full v1.

Design principle:
- do not maximize A/B/C independently
- preserve the existing Full v1 flow first
- A: when livestock feed is under pressure, do not divert labor into fertilizer
- C: only a hand that Full v1 already assigned PASS is considered spare capacity
- B: use that spare capacity to recycle at most one fertilizer unit into a useful crop

The wrapper therefore adds work only into visible slack. It does not replace an
existing productive Full v1 hand action, change crop targets, change cow targets,
or add market prediction.
"""

import copy

import full_strong_origin_v1 as base

FERTILIZER_RESERVE = 1

_STATS = {
    "turns": 0,
    "feed_pressure_turns": 0,
    "slack_hand_turns": 0,
    "fertilizer_sell_units_withheld": 0,
    "fertilizer_pickups": 0,
    "fertilize_actions": 0,
    "fertilizer_moves": 0,
    "fertilizer_skipped_no_slack": 0,
    "fertilizer_skipped_feed_pressure": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["whole_v2"] = dict(_STATS)
    data["whole_v2"]["fertilizer_reserve"] = FERTILIZER_RESERVE
    data["whole_v2"]["composition"] = "feed-first + idle-hand-only fertilizer recycling"
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
    """Visible crop targets only; no price or future-state prediction."""
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
            # Prefer crops already inside an active production window.
            if crop == "STRAWBERRY":
                targets.append((0, x, y))
            elif crop == "MELON" and 6 <= age <= 12:
                targets.append((1, x, y))
            elif crop == "WHEAT" and 2 <= age <= 4:
                targets.append((2, x, y))
    targets.sort()
    return [(x, y) for _, x, y in targets]


def _feed_pressure(obs):
    """Reuse Full v1/G8's visible feed concept: wheat stock vs two per cow."""
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

    targets = _fertilizer_targets(obs)
    if not targets or not hands:
        return action

    if _feed_pressure(obs):
        _STATS["feed_pressure_turns"] += 1
        _STATS["fertilizer_skipped_feed_pressure"] += 1
        return action

    hand_actions = list(action.get("hands", []))
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])

    # Flow-preserving rule: fertilizer may use only capacity that Full v1 did
    # not already assign to another task this turn.
    idle = [i for i, a in enumerate(hand_actions) if not a or a[0] == "PASS"]
    if not idle:
        _STATS["fertilizer_skipped_no_slack"] += 1
        return action
    _STATS["slack_hand_turns"] += 1

    # Prefer an idle hand already carrying fertilizer; otherwise choose the idle
    # hand closest to the shed. No productive Full v1 action is replaced.
    while len(inventories) < 1 + len(hands):
        inventories.append({})

    carrying = [i for i in idle if int(inventories[i + 1].get("FERTILIZER", 0)) > 0]
    if carrying:
        hand_index = min(carrying, key=lambda i: min(abs(hands[i][0]-x)+abs(hands[i][1]-y) for x, y in targets))
        pos = tuple(hands[hand_index])
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

    # Only now retain one unit from the existing sell order. If there is no
    # spare labor this turn, fertilizer is sold exactly as in Full v1.
    action["market"] = _retain_one_fertilizer(action.get("market", []), shed_fert)

    h = board_size // 2
    shed_points = [(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)]
    hand_index = min(idle, key=lambda i: min(abs(hands[i][0]-x)+abs(hands[i][1]-y) for x, y in shed_points))
    pos = tuple(hands[hand_index])
    if _adjacent_shed(pos[0], pos[1], board_size):
        hand_actions[hand_index] = ["PICKUP", "FERTILIZER", 1]
        _STATS["fertilizer_pickups"] += 1
    else:
        hand_actions[hand_index] = _move_toward(pos, _nearest(pos, shed_points))
        _STATS["fertilizer_moves"] += 1

    action["hands"] = hand_actions
    return action
