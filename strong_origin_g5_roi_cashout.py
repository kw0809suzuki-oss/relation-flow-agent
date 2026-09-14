"""Public candidate: G5 + investment ROI + late reinvestment cash-out.

The baseline is strong_origin_g5_roi. This wrapper changes one design unit only:
late crop reinvestment. Existing Strong Origin behavior, G5 coordination, and
investment ROI filtering remain untouched.

The cutoff is observation-time only and follows conservative crop-horizon
windows already visible in strong public Kaggriculture agents:
- WHEAT: last new seed buy on day 24
- STRAWBERRY: last new seed buy on day 14
- MELON: last new seed buy on day 16

The base agent already sells shed inventory every turn; this candidate simply
stops late capital from re-entering crops whose remaining horizon is short.
No seed id, paired result, terminal reward, or future state is used at runtime.
"""

import copy

import strong_origin_g5_roi as base

LAST_BUY_DAY = {
    "WHEAT": 24,
    "STRAWBERRY": 14,
    "MELON": 16,
}

_CASHOUT = {
    "seed_orders_kept": 0,
    "seed_orders_filtered": 0,
    "seed_units_kept": 0,
    "seed_units_filtered": 0,
    "filtered_by_crop": {crop: 0 for crop in LAST_BUY_DAY},
}


def reset_telemetry():
    base.reset_telemetry()
    _CASHOUT["seed_orders_kept"] = 0
    _CASHOUT["seed_orders_filtered"] = 0
    _CASHOUT["seed_units_kept"] = 0
    _CASHOUT["seed_units_filtered"] = 0
    _CASHOUT["filtered_by_crop"] = {crop: 0 for crop in LAST_BUY_DAY}


def get_telemetry():
    data = dict(base.get_telemetry())
    data["cashout"] = {
        "seed_orders_kept": _CASHOUT["seed_orders_kept"],
        "seed_orders_filtered": _CASHOUT["seed_orders_filtered"],
        "seed_units_kept": _CASHOUT["seed_units_kept"],
        "seed_units_filtered": _CASHOUT["seed_units_filtered"],
        "filtered_by_crop": dict(_CASHOUT["filtered_by_crop"]),
    }
    return data


def agent(obs):
    action = copy.deepcopy(base.agent(obs))
    day = int(obs["day"])
    market = []
    for item in action.get("market", []):
        if not item or item[0] != "BUY_SEED":
            market.append(item)
            continue

        crop = item[1]
        units = int(item[2]) if len(item) > 2 else 0
        cutoff = LAST_BUY_DAY.get(crop)
        if cutoff is not None and day > cutoff:
            _CASHOUT["seed_orders_filtered"] += 1
            _CASHOUT["seed_units_filtered"] += units
            _CASHOUT["filtered_by_crop"][crop] += units
            continue

        _CASHOUT["seed_orders_kept"] += 1
        _CASHOUT["seed_units_kept"] += units
        market.append(item)

    action["market"] = market
    return action
