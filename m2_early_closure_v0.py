"""M2 Early Closure v0.

Experimental bias only:
- From day >= EARLY_CLOSURE_DAY, suppress new expansion purchases.
- Preserve SELL, HIRE, movement/work actions, and all pre-existing assets.
- Native policy remains G17; this wrapper only post-processes the market bundle.

This is not an adopted rule. Day 20 is an explicit test knob, not a discovered optimum.
"""
import copy
import g17_agent as native

EARLY_CLOSURE_DAY = 20

_activations = []


def reset_experiment():
    global _activations
    _activations = []
    native.reset_telemetry()


def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)


def _is_expansion_purchase(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    op = action[0]
    if op in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL"):
        return True
    # Legacy/current variants may encode COW as BUY_PRODUCT COW.
    if op == "BUY_PRODUCT" and len(action) > 1 and action[1] == "COW":
        return True
    return False


def agent(obs):
    actions = native.agent(obs)
    day = int(obs.get("day", 0) or 0)

    if day < EARLY_CLOSURE_DAY or not isinstance(actions, dict):
        return actions

    market = list(actions.get("market", []) or [])
    removed = [a for a in market if _is_expansion_purchase(a)]
    if not removed:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if not _is_expansion_purchase(a)]
    _activations.append({
        "day": day,
        "removed": copy.deepcopy(removed),
        "before_market": copy.deepcopy(market),
        "after_market": copy.deepcopy(revised["market"]),
    })
    return revised


def get_activations():
    return copy.deepcopy(_activations)


def get_trace():
    return native.get_trace()
