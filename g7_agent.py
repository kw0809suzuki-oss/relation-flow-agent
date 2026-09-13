"""G7 provisional compound cash-cycle wrapper.

Hypothesis from external observation:
strong agents separate around day 10-15 when several revenue loops begin
turning inventory into cash and cash back into productive capacity.
"""

import agent as base

_CURRENT_UNITS = 4


def reset_telemetry():
    return base.reset_telemetry()


def get_telemetry():
    return base.get_telemetry()


def _compound_targets(name, day, capacity):
    s = base.STRATEGIES[name]
    if day < 7 and name not in ("ENDGAME", "LIQUID"):
        usable = min(capacity, max(8, min(14, _CURRENT_UNITS * 3)))
        mix = {"WHEAT": 0.75, "MELON": 0.25, "STRAWBERRY": 0.0}
    elif day < 16 and name not in ("ENDGAME", "LIQUID"):
        usable = min(capacity, max(12, min(32, _CURRENT_UNITS * 4)))
        mix = {"WHEAT": 0.55, "MELON": 0.15, "STRAWBERRY": 0.30}
    elif day >= 24:
        usable = max(8, int(capacity * s["occupancy_target"]))
        mix = {"WHEAT": 0.82, "MELON": 0.18, "STRAWBERRY": 0.0}
    else:
        usable = max(8, int(capacity * s["occupancy_target"]))
        mix = dict(s["mix"])
    return {c: int(usable * w) for c, w in mix.items()}


def agent(obs):
    global _CURRENT_UNITS
    me = obs["farms"][obs["player"]]
    day = obs["day"]
    _CURRENT_UNITS = 1 + len(me.get("hands", []))
    old_origin_targets = base.origin_targets
    old_wheat_max_day = base.MAX_YIELD_DAY["WHEAT"]
    old_settings = {k: (v["reserve_base"], v["max_units"]) for k, v in base.STRATEGIES.items()}
    try:
        base.origin_targets = _compound_targets
        if day < 16:
            base.MAX_YIELD_DAY["WHEAT"] = 2
        if day < 7:
            reserve = 250
            max_units = 11
        elif day < 16:
            reserve = 350
            max_units = 13
        else:
            reserve = None
            max_units = None
        if reserve is not None:
            for name in ("BALANCED", "CROP_RUSH"):
                base.STRATEGIES[name]["reserve_base"] = reserve
                base.STRATEGIES[name]["max_units"] = max(base.STRATEGIES[name]["max_units"], max_units)
        return base.agent(obs)
    finally:
        base.origin_targets = old_origin_targets
        base.MAX_YIELD_DAY["WHEAT"] = old_wheat_max_day
        for k, (reserve_base, max_units0) in old_settings.items():
            base.STRATEGIES[k]["reserve_base"] = reserve_base
            base.STRATEGIES[k]["max_units"] = max_units0
