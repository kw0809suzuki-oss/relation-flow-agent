"""Public candidate: G5 coordinated Strong Origin + observable investment ROI gate.

This module deliberately wraps strong_origin_g5 rather than rewriting it.
The only design-unit change is investment filtering:
- BUY_LAND is kept only when a conservative observable payback proxy exceeds cost.
- HIRE is kept only when remaining visible work/horizon plausibly pays back the hire.

No seed, paired result, terminal reward, or future state is used at runtime.
"""

import copy

import strong_origin_g5 as base

BASE_PRICE = base.BASE_PRICE
SEED_COST = base.SEED_COST

_ROI = {
    "land_kept": 0,
    "land_filtered": 0,
    "hire_kept": 0,
    "hire_filtered": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for key in _ROI:
        _ROI[key] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["investment_roi"] = dict(_ROI)
    return data


def _visible_work(obs):
    me = obs["farms"][obs["player"]]
    day = obs["day"]
    work = 0
    empty = 0
    locked = 0
    for row in me.get("tiles", []):
        for tile in row:
            if tile == "LOCKED":
                locked += 1
                continue
            if tile is None:
                empty += 1
                continue
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "WEED":
                work += 1
            elif kind == "PLANT":
                crop = tile.get("crop")
                age = day - tile.get("planted_day", day)
                if not tile.get("watered_today", False):
                    work += 1
                if tile.get("yield_units", 0) > 0 and (
                    crop == "STRAWBERRY" or age >= base.MAX_YIELD_DAY.get(crop, 10 ** 9)
                ):
                    work += 1
    return work, empty, locked


def _best_net_per_tile(obs):
    prices = obs.get("market", {}).get("prices", {})
    nets = []
    for crop in BASE_PRICE:
        sale = float(prices.get(crop, BASE_PRICE[crop]))
        nets.append(max(0.0, sale - SEED_COST[crop]))
    return max(nets, default=0.0)


def _keep_land(obs):
    me = obs["farms"][obs["player"]]
    remaining_days = max(0, 30 - obs["day"])
    quadrants = len(me.get("unlocked_quadrants", []))
    cost = {1: 1000, 2: 2000, 3: 4000}.get(quadrants)
    if not cost:
        return False
    _, _, locked = _visible_work(obs)
    extra_tiles = min(16, locked)
    if extra_tiles <= 0:
        return False
    # Conservative horizon proxy: assume at most one monetizable crop cycle per
    # ~10 days and discount gross crop spread to 35% for watering/movement risk.
    cycles = max(0, remaining_days // 10)
    expected_return = extra_tiles * _best_net_per_tile(obs) * cycles * 0.35
    return expected_return > cost


def _keep_hire(obs):
    me = obs["farms"][obs["player"]]
    remaining_days = max(0, 30 - obs["day"])
    current_units = 1 + len(me.get("hands", []))
    hires_today = int(me.get("hires_today", 0))
    cost = float(base.fib_hire_cost(hires_today))
    work, empty, _ = _visible_work(obs)
    visible_pressure = work + min(empty, current_units * 2)
    surplus = max(0, visible_pressure - current_units)
    # Reuse the old Strong-Origin action-value scale, but require a finite
    # remaining-horizon payback instead of a cost-only threshold.
    expected_uses = min(remaining_days, 12) * min(1.0, surplus / max(1, current_units))
    expected_return = expected_uses * 50.0
    return expected_return > cost


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    market = []
    for item in action.get("market", []):
        if not item:
            market.append(item)
            continue
        kind = item[0]
        if kind == "BUY_LAND":
            if _keep_land(obs):
                _ROI["land_kept"] += 1
                market.append(item)
            else:
                _ROI["land_filtered"] += 1
        elif kind == "HIRE":
            if _keep_hire(obs):
                _ROI["hire_kept"] += 1
                market.append(item)
            else:
                _ROI["hire_filtered"] += 1
        else:
            market.append(item)
    action["market"] = market
    return action
