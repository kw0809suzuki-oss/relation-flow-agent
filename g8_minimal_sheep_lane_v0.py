"""Minimal SHEEP Lane Probe v0 livestock overlay.

Starts from frozen G8 behavior and adds exactly one early SHEEP lane after the
existing two-COW target is economically reachable. Generic animal servicing
(HARVEST / FEED / CARE / FERTILIZER / DROP) is reused.

This module is experimental and is only swapped into Body-only by the probe
wrapper; g8_agent.py remains unchanged.
"""

import g7_agent as g7

ANIMAL_COST = {"COW": 400, "SHEEP": 500}
SHEEP_TARGET = 1
SHEEP_ENTRY_END_DAY = 4
POST_ANIMAL_CASH_FLOOR = 700
FEED_CARRY = 3
COW_TARGETS = ((6, 2), (10, 4), (16, 6))


def reset_telemetry():
    return g7.reset_telemetry()


def get_telemetry():
    return g7.get_telemetry()


def _adjacent_shed(x, y, board_size):
    h = board_size // 2
    return (x, y) in {(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)}


def _move_toward(src, dst):
    x, y = src
    tx, ty = dst
    if x < tx: return ["EAST"]
    if x > tx: return ["WEST"]
    if y < ty: return ["SOUTH"]
    if y > ty: return ["NORTH"]
    return ["PASS"]


def _nearest(src, points):
    if not points:
        return None
    x, y = src
    return min(points, key=lambda p: abs(p[0] - x) + abs(p[1] - y))


def _cow_target(day):
    for before, target in COW_TARGETS:
        if day < before:
            return target
    return 0


def agent(obs):
    base_action = g7.agent(obs)
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    tiles = me["tiles"]
    board_size = len(tiles)
    day = obs["day"]
    prices = obs.get("market", {}).get("prices", {})
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])

    animal_tiles = []
    empty_pastures = []
    empty_tiles = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if tile is None:
                empty_tiles.append((x, y)); continue
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PASTURE":
                if tile.get("animal"):
                    animal_tiles.append((x, y, tile))
                else:
                    empty_pastures.append((x, y))

    carried_cows = sum(inv.get("COW", 0) for inv in inventories)
    carried_sheep = sum(inv.get("SHEEP", 0) for inv in inventories)
    carried_wheat = sum(inv.get("WHEAT", 0) for inv in inventories)
    cows_on_farm = sum(1 for _, _, t in animal_tiles if t.get("animal") == "COW")
    sheep_on_farm = sum(1 for _, _, t in animal_tiles if t.get("animal") == "SHEEP")
    total_cows = cows_on_farm + shed.get("COW", 0) + carried_cows
    total_sheep = sheep_on_farm + shed.get("SHEEP", 0) + carried_sheep

    sells = [o for o in base_action.get("market", []) if o and o[0] == "SELL"]
    others = [o for o in base_action.get("market", []) if o and o[0] != "SELL"]
    market = list(sells)
    sale_cash = sum(prices.get(o[1], 0) * o[2] for o in sells if len(o) >= 3)
    available_cash = me.get("money", 0) + sale_cash

    target_cows = _cow_target(day)
    cow_added = 0
    if target_cows and total_cows < target_cows and available_cash >= 1100 and len(market) < 10:
        market.append(["BUY_ANIMAL", "COW", 1])
        available_cash -= ANIMAL_COST["COW"]
        cow_added = 1

    # Probe-only missing lane: preserve the native two-COW entrance, then add
    # exactly one SHEEP while reusing the same 700-Cash post-animal floor that
    # is implicit in G8's 1100-before-400-COW condition.
    projected_cows = total_cows + cow_added
    if (
        day <= SHEEP_ENTRY_END_DAY
        and total_sheep < SHEEP_TARGET
        and projected_cows >= 2
        and available_cash - ANIMAL_COST["SHEEP"] >= POST_ANIMAL_CASH_FLOOR
        and len(market) < 10
    ):
        market.append(["BUY_ANIMAL", "SHEEP", 1])
        available_cash -= ANIMAL_COST["SHEEP"]

    feed_stock = shed.get("WHEAT", 0) + carried_wheat
    feed_target = max(0, (total_cows + total_sheep + cow_added) * 2)
    if total_cows > 0 and feed_stock < feed_target and len(market) < 10:
        buy = min(12, feed_target - feed_stock)
        wheat_price = max(1, prices.get("WHEAT", 25))
        affordable = int(max(0, available_cash - 350) // wheat_price)
        buy = min(buy, affordable)
        if buy > 0:
            market.append(["BUY_PRODUCT", "WHEAT", buy])
            available_cash -= buy * wheat_price

    for order in sorted(others, key=lambda o: 0 if o[0] == "HIRE" else (1 if o[0] == "BUY_LAND" else 2)):
        if len(market) >= 10:
            break
        market.append(order)

    unit_positions = [me["farmer"]] + list(me.get("hands", []))
    while len(inventories) < len(unit_positions):
        inventories = list(inventories) + [{}]
    lane = min(3, len(unit_positions))
    reserved_animals = set()
    reserved_build = set()
    reserved_sheep_pickups = [0]

    def livestock_action(idx, pos):
        x, y = pos
        inv = inventories[idx] if idx < len(inventories) else {}
        tile = tiles[y][x]
        produce = sum(inv.get(k, 0) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
        if produce > 0:
            if _adjacent_shed(x, y, board_size):
                return ["DROP"]
            h = board_size // 2
            return _move_toward((x, y), _nearest((x, y), [(h-1,h-1),(h,h-1),(h-1,h),(h,h)]))
        carried_animal = "SHEEP" if inv.get("SHEEP", 0) > 0 else ("COW" if inv.get("COW", 0) > 0 else None)
        if carried_animal is not None:
            if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and not tile.get("animal"):
                return ["PLACE", carried_animal, 1]
            target = _nearest((x, y), [p for p in empty_pastures if p not in reserved_build])
            if target is not None:
                reserved_build.add(target); return _move_toward((x, y), target)
            if tile is None:
                reserved_build.add((x, y)); return ["BUILD_PASTURE"]
            target = _nearest((x, y), [p for p in empty_tiles if p not in reserved_build])
            if target is not None:
                reserved_build.add(target); return _move_toward((x, y), target)
        if isinstance(tile, dict) and tile.get("animal") == "COW":
            if tile.get("yield_units", 0) > 0:
                reserved_animals.add((x, y)); return ["HARVEST"]
            if not tile.get("fed_today", False) and inv.get("WHEAT", 0) > 0:
                reserved_animals.add((x, y)); return ["FEED"]
            if tile.get("fed_today", False) and not tile.get("cared_today", False):
                reserved_animals.add((x, y)); return ["CARE"]
            if tile.get("fertilizer_available", False):
                reserved_animals.add((x, y)); return ["COLLECT_FERTILIZER"]
        if inv.get("WHEAT", 0) > 0:
            sheep_needs_feed = [
                (ax, ay) for ax, ay, t in animal_tiles
                if t.get("animal") == "SHEEP"
                and not t.get("fed_today", False)
                and (ax, ay) not in reserved_animals
            ]
            needs_feed = [
                (ax, ay) for ax, ay, t in animal_tiles
                if not t.get("fed_today", False)
                and (ax, ay) not in reserved_animals
            ]
            target = _nearest((x, y), sheep_needs_feed) or _nearest((x, y), needs_feed)
            if target is not None:
                reserved_animals.add(target); return _move_toward((x, y), target)
        if _adjacent_shed(x, y, board_size):
            available_sheep = max(0, shed.get("SHEEP", 0) - reserved_sheep_pickups[0])
            if available_sheep > 0 and (empty_pastures or empty_tiles):
                reserved_sheep_pickups[0] += 1
                return ["PICKUP", "SHEEP", 1]
            if shed.get("COW", 0) > 0 and (empty_pastures or empty_tiles):
                return ["PICKUP", "COW", 1]
            needs_feed_count = sum(1 for _, _, t in animal_tiles if not t.get("fed_today", False))
            if needs_feed_count and shed.get("WHEAT", 0) > 0:
                return ["PICKUP", "WHEAT", min(FEED_CARRY, shed.get("WHEAT", 0))]
        sheep_task_tiles = []
        task_tiles = []
        for ax, ay, t in animal_tiles:
            if (ax, ay) in reserved_animals: continue
            if t.get("yield_units", 0) > 0 or not t.get("fed_today", False) or not t.get("cared_today", False) or t.get("fertilizer_available", False):
                task_tiles.append((ax, ay))
                if t.get("animal") == "SHEEP" and not t.get("fed_today", False):
                    sheep_task_tiles.append((ax, ay))
        target = _nearest((x, y), sheep_task_tiles) or _nearest((x, y), task_tiles)
        if target is not None:
            reserved_animals.add(target)
            tt = tiles[target[1]][target[0]]
            if not tt.get("fed_today", False) and inv.get("WHEAT", 0) <= 0:
                h = board_size // 2
                shed_pos = _nearest((x, y), [(h-1,h-1),(h,h-1),(h-1,h),(h,h)])
                if not _adjacent_shed(x, y, board_size):
                    return _move_toward((x, y), shed_pos)
            return _move_toward((x, y), target)
        return None

    farmer_action = base_action.get("farmer", ["PASS"])
    hand_actions = list(base_action.get("hands", []))
    while len(hand_actions) < len(me.get("hands", [])):
        hand_actions.append(["PASS"])
    for idx in range(lane):
        override = livestock_action(idx, unit_positions[idx])
        if override is None: continue
        if idx == 0: farmer_action = override
        else: hand_actions[idx - 1] = override
    return {"farmer": farmer_action, "hands": hand_actions, "market": market}
