"""G8: compose a real livestock revenue loop over G7."""

import g7_agent as g7
from kaggle_environments.envs.kaggriculture.kaggriculture import market_price as official_market_price

ANIMAL_COST = {"COW": 400}
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


def _self_only_sell_projection(obs, sells):
    """Project only our SELL orders with the official per-unit price function.

    Boundary: opponent actions and same-turn unit-action shed changes are unknown
    at decision time, so this is not a prediction of the actual market result.
    """
    market = obs.get("market", {}) or {}
    inventory = dict(market.get("inventory", {}) or {})
    params = market.get("params")
    available = dict(obs.get("private", {}).get("shed", {}) or {})
    cash = 0
    sold_units = 0

    for order in sells:
        if len(order) < 3:
            continue
        item = order[1]
        remaining = max(0, min(int(order[2]), int(available.get(item, 0))))
        for _ in range(remaining):
            if item not in inventory:
                break
            inv = inventory[item]
            price = official_market_price(item, inv, params)
            cash += price
            available[item] = max(0, available.get(item, 0) - 1)
            sold_units += 1
            if price > 1:
                inventory[item] = inv + 1
    return cash, inventory, sold_units


def _self_only_wheat_buy_capacity(inventory, params, cash, requested, shed_room, reserve=350):
    """Use the official BUY_PRODUCT quote rule for our own projected units only."""
    inv = inventory.get("WHEAT")
    if inv is None:
        return 0, 0
    count = 0
    spent = 0
    limit = max(0, min(int(requested), int(shed_room)))
    for _ in range(limit):
        price = official_market_price("WHEAT", inv - 1, params)
        if cash - spent - price < reserve:
            break
        spent += price
        inv -= 1
        count += 1
    inventory["WHEAT"] = inv
    return count, spent


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
    carried_wheat = sum(inv.get("WHEAT", 0) for inv in inventories)
    cows_on_farm = sum(1 for _, _, t in animal_tiles if t.get("animal") == "COW")
    total_cows = cows_on_farm + shed.get("COW", 0) + carried_cows

    sells = [o for o in base_action.get("market", []) if o and o[0] == "SELL"]
    others = [o for o in base_action.get("market", []) if o and o[0] != "SELL"]
    market = list(sells)
    sale_cash, projected_inventory, projected_sold_units = _self_only_sell_projection(obs, sells)
    available_cash = me.get("money", 0) + sale_cash
    projected_shed_count = max(0, sum(shed.values()) - projected_sold_units)

    target_cows = _cow_target(day)
    if target_cows and total_cows < target_cows and available_cash >= 1100 and len(market) < 10:
        market.append(["BUY_ANIMAL", "COW", 1])
        available_cash -= ANIMAL_COST["COW"]
        projected_shed_count += 1

    feed_stock = shed.get("WHEAT", 0) + carried_wheat
    feed_target = max(0, total_cows * 2)
    if total_cows > 0 and feed_stock < feed_target and len(market) < 10:
        requested = min(12, feed_target - feed_stock)
        market_state = obs.get("market", {}) or {}
        shed_room = max(0, 100 - projected_shed_count)
        buy, buy_cost = _self_only_wheat_buy_capacity(
            projected_inventory,
            market_state.get("params"),
            available_cash,
            requested,
            shed_room,
        )
        if buy > 0:
            market.append(["BUY_PRODUCT", "WHEAT", buy])
            available_cash -= buy_cost
            projected_shed_count += buy

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
        if inv.get("COW", 0) > 0:
            if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and not tile.get("animal"):
                return ["PLACE", "COW", 1]
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
            needs_feed = [(ax, ay) for ax, ay, t in animal_tiles if not t.get("fed_today", False) and (ax, ay) not in reserved_animals]
            target = _nearest((x, y), needs_feed)
            if target is not None:
                reserved_animals.add(target); return _move_toward((x, y), target)
        if _adjacent_shed(x, y, board_size):
            if shed.get("COW", 0) > 0 and (empty_pastures or empty_tiles):
                return ["PICKUP", "COW", 1]
            needs_feed_count = sum(1 for _, _, t in animal_tiles if not t.get("fed_today", False))
            if needs_feed_count and shed.get("WHEAT", 0) > 0:
                return ["PICKUP", "WHEAT", min(FEED_CARRY, shed.get("WHEAT", 0))]
        task_tiles = []
        for ax, ay, t in animal_tiles:
            if (ax, ay) in reserved_animals: continue
            if t.get("yield_units", 0) > 0 or not t.get("fed_today", False) or not t.get("cared_today", False) or t.get("fertilizer_available", False):
                task_tiles.append((ax, ay))
        target = _nearest((x, y), task_tiles)
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
