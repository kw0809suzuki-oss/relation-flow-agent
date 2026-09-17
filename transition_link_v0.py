"""Transition Link v0 — minimal operational hypothesis.

Keep frozen v6 intact. Let v6 produce its normal candidate Action, then apply one
small footprint-aware override: when v6 schedules SELLs, treat the current
pre-action market value of those SELLs as near-cash for same-turn investment
headroom. This tests the observed connection:

State -> candidate Action -> market/value footprint -> investment Action -> next State.

This is deliberately not a terminal predictor and not a general simulator.
"""
import strong_origin as v6


def _sell_value(obs, market_actions):
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    value = 0.0
    for a in market_actions or []:
        if not isinstance(a, (list, tuple)) or len(a) < 3 or a[0] != "SELL":
            continue
        item, qty = str(a[1]), a[2]
        price = prices.get(item)
        if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
            value += float(qty) * float(price)
    return value


def agent(obs):
    candidate = v6.agent(obs)
    market = list(candidate.get("market", []) or [])
    if not market or len(market) >= 10:
        return candidate

    player = obs["player"]
    me = obs["farms"][player]
    day = int(obs.get("day", 0))
    remaining_days = 30 - day

    # One-link hypothesis only: scheduled liquidation can fund a same-turn LAND
    # purchase that v6 rejected because projected_cash only used current money.
    # Preserve all original v6 gates except the cash timing connection.
    sell_value = _sell_value(obs, market)
    if sell_value <= 0:
        return candidate

    quadrants = len(me.get("unlocked_quadrants", []))
    land_cost = {1: 1000, 2: 2000, 3: 4000}.get(quadrants)
    if not land_cost or remaining_days < 9 or any(a and a[0] == "BUY_LAND" for a in market):
        return candidate

    # Reconstruct only the stable reserve component available from observation.
    tiles = me.get("tiles", []) or []
    unlocked = 0
    empty = 0
    for row in tiles:
        for tile in row:
            if tile != "LOCKED":
                unlocked += 1
                if tile is None:
                    empty += 1
    occupied = unlocked - empty

    # Determine v6 strategy exactly enough to preserve its reserve/occupancy gate.
    opp = obs["farms"][1-player]
    from x_engine import XField, choose_x_origin
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    my_supply = {c: 0 for c in v6.BASE_PRICE}
    opp_supply = {c: 0 for c in v6.BASE_PRICE}
    for row in tiles:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") in my_supply:
                my_supply[tile["crop"]] += 1
    for row in opp.get("tiles", []) or []:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") in opp_supply:
                opp_supply[tile["crop"]] += 1
    field = XField(day=day, remaining_days=remaining_days, my_money=me.get("money",0), opp_money=opp.get("money",0),
        my_land=quadrants, opp_land=len(opp.get("unlocked_quadrants",[])), my_hands=len(me.get("hands",[])),
        opp_hands=len(opp.get("hands",[])), prices=prices, my_supply=my_supply, opp_supply=opp_supply)
    strategy_name = choose_x_origin(field, v6.BASE_PRICE).origin
    strategy = v6.STRATEGIES[strategy_name]
    occupancy = occupied / unlocked if unlocked else 1.0
    reserve = strategy["reserve_base"] + 20 * occupied

    if strategy_name in ("LIQUID", "ENDGAME") or occupancy < strategy["occupancy_target"]:
        return candidate

    effective_cash = float(me.get("money", 0)) + sell_value
    if effective_cash - land_cost >= reserve:
        # SELLs are already ahead of investments in v6's market list. Insert LAND
        # immediately after the final SELL, before seed/hire actions consume cash.
        last_sell = max(i for i, a in enumerate(market) if a and a[0] == "SELL")
        market.insert(last_sell + 1, ["BUY_LAND"])
        candidate = dict(candidate)
        candidate["market"] = market[:10]
    return candidate
