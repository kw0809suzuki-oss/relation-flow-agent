"""Expansion Cycle Candidate v0.

Observation-derived experimental wrapper over the current Combat Model.

Scope:
- Active only on day 7.
- Requires at least two unlocked quadrants.
- Does not force BUY_LAND.
- Tries to convert already-owned expansion capacity into production by:
  1) raising hands toward 8 when affordable,
  2) ensuring one MELON seed when affordable,
  3) steering one hand to an empty NE tile and planting MELON once reachable.

This is an experiment, not an adopted rule.
"""

import copy
import whole_flow_control_agent as native
from strong_origin import fib_hire_cost, SEED_COST

ACTIVE_DAY = 7
TARGET_HANDS = 8
TARGET_CROP = "MELON"

_state = {}

def reset_experiment():
    global _state
    _state = {
        "eligible_calls": 0,
        "hire_orders_added": 0,
        "seed_orders_added": 0,
        "steer_overrides": 0,
        "plant_overrides": 0,
        "events": [],
    }
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def _market_projection(obs, market):
    p = int(obs["player"])
    me = obs["farms"][p]
    money = float(me.get("money", 0) or 0)
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    hires = int(me.get("hires_today", 0) or 0)
    quadrants = len(me.get("unlocked_quadrants", []) or [])
    seed_cost = {"WHEAT":10, "STRAWBERRY":100, "MELON":80}
    animal_cost = {"COW":400}
    for order in market:
        if not isinstance(order, (list, tuple)) or not order:
            continue
        op = order[0]
        if op == "SELL" and len(order) >= 3:
            money += float(prices.get(order[1], 0) or 0) * float(order[2] or 0)
        elif op == "BUY_PRODUCT" and len(order) >= 3:
            money -= float(prices.get(order[1], 0) or 0) * float(order[2] or 0)
        elif op == "BUY_SEED" and len(order) >= 3:
            money -= seed_cost.get(order[1], 0) * float(order[2] or 0)
        elif op == "BUY_ANIMAL" and len(order) >= 3:
            money -= animal_cost.get(order[1], 0) * float(order[2] or 0)
        elif op == "BUY_LAND":
            money -= {1:1000, 2:2000, 3:4000}.get(quadrants, 0)
            quadrants += 1
        elif op == "HIRE":
            money -= fib_hire_cost(hires)
            hires += 1
    return money, hires

def _ne_empty_tiles(me):
    tiles = me.get("tiles", []) or []
    if not tiles:
        return []
    h = len(tiles) // 2
    out = []
    for y in range(min(h, len(tiles))):
        row = tiles[y] or []
        for x in range(h, len(row)):
            if row[x] is None:
                out.append((x, y))
    return out

def _has_ne_melon(me):
    tiles = me.get("tiles", []) or []
    if not tiles:
        return False
    h = len(tiles) // 2
    for y in range(min(h, len(tiles))):
        row = tiles[y] or []
        for x in range(h, len(row)):
            tile = row[x]
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == TARGET_CROP:
                return True
    return False

def _move(src, dst):
    x, y = src
    tx, ty = dst
    if x < tx: return ["EAST"]
    if x > tx: return ["WEST"]
    if y < ty: return ["SOUTH"]
    if y > ty: return ["NORTH"]
    return ["PASS"]

def agent(obs):
    if not _state:
        reset_experiment()

    actions = native.agent(obs)
    if not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    p = int(obs["player"])
    me = obs["farms"][p]
    quadrants = len(me.get("unlocked_quadrants", []) or [])
    if day != ACTIVE_DAY or quadrants < 2:
        return actions

    _state["eligible_calls"] += 1
    revised = copy.deepcopy(actions)
    market = list(revised.get("market", []) or [])
    before_market = copy.deepcopy(market)
    projected_cash, projected_hires_today = _market_projection(obs, market)
    current_hands = len(me.get("hands", []) or [])
    existing_hires = sum(1 for a in market if isinstance(a, (list, tuple)) and a and a[0] == "HIRE")
    projected_hands = current_hands + existing_hires

    private = obs.get("private", {}) or {}
    melon_seeds = int((private.get("seeds", {}) or {}).get(TARGET_CROP, 0) or 0)
    existing_seed_order = sum(
        int(a[2])
        for a in market
        if isinstance(a, (list, tuple)) and len(a) >= 3 and a[0] == "BUY_SEED" and a[1] == TARGET_CROP
    )

    seed_added = False
    if melon_seeds + existing_seed_order <= 0 and len(market) < 10 and projected_cash >= SEED_COST[TARGET_CROP]:
        market.append(["BUY_SEED", TARGET_CROP, 1])
        projected_cash -= SEED_COST[TARGET_CROP]
        seed_added = True
        _state["seed_orders_added"] += 1

    hires_added = 0
    while projected_hands < TARGET_HANDS and len(market) < 10:
        cost = fib_hire_cost(projected_hires_today)
        if projected_cash < cost:
            break
        market.append(["HIRE"])
        projected_cash -= cost
        projected_hires_today += 1
        projected_hands += 1
        hires_added += 1
        _state["hire_orders_added"] += 1

    revised["market"] = market

    plant_override = None
    steer_override = None
    if not _has_ne_melon(me) and melon_seeds > 0:
        empty = _ne_empty_tiles(me)
        hands = list(me.get("hands", []) or [])
        if empty and hands:
            best = None
            for idx, pos in enumerate(hands):
                if not isinstance(pos, (list, tuple)) or len(pos) < 2:
                    continue
                for target in empty:
                    dist = abs(pos[0] - target[0]) + abs(pos[1] - target[1])
                    cand = (dist, idx, tuple(pos), target)
                    if best is None or cand < best:
                        best = cand
            if best is not None:
                _, idx, pos, target = best
                hand_actions = list(revised.get("hands", []) or [])
                while len(hand_actions) < len(hands):
                    hand_actions.append(["PASS"])
                if tuple(pos) == tuple(target):
                    hand_actions[idx] = ["PLANT", TARGET_CROP]
                    plant_override = {"hand_index": idx, "position": list(pos), "target": list(target)}
                    _state["plant_overrides"] += 1
                else:
                    hand_actions[idx] = _move(pos, target)
                    steer_override = {"hand_index": idx, "position": list(pos), "target": list(target), "action": hand_actions[idx]}
                    _state["steer_overrides"] += 1
                revised["hands"] = hand_actions

    if hires_added or seed_added or plant_override or steer_override:
        _state["events"].append({
            "day": day,
            "money": me.get("money"),
            "hands": current_hands,
            "quadrants": quadrants,
            "before_market": before_market,
            "after_market": copy.deepcopy(market),
            "hires_added": hires_added,
            "seed_added": seed_added,
            "plant_override": plant_override,
            "steer_override": steer_override,
        })

    return revised

def get_experiment_telemetry():
    return copy.deepcopy(_state)

def get_trace():
    return native.get_trace()
