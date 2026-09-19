"""Closure switch timing sweep v0 over frozen G17 Current.

Single experimental knob:
- from switch_day onward, suppress all new expansion purchases.
No other policy change.
"""
import copy
import g17_agent as native

_active_day = None
_activations = []

def set_switch_day(day):
    global _active_day
    _active_day = day

def reset_experiment():
    global _activations
    _activations = []
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def get_activations():
    return copy.deepcopy(_activations)

def get_trace():
    return native.get_trace()

def _op(a):
    return a[0] if isinstance(a, (list, tuple)) and a else None

def _is_expansion(a):
    if not isinstance(a, (list, tuple)) or not a:
        return False
    op = a[0]
    if op in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(a) > 1 and a[1] == "COW"

def agent(obs):
    actions = native.agent(obs)
    if _active_day is None or not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    if day < _active_day:
        return actions

    market = list(actions.get("market", []) or [])
    removed = [a for a in market if _is_expansion(a)]
    if not removed:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if not _is_expansion(a)]
    _activations.append({
        "switch_day": _active_day,
        "day": day,
        "removed": copy.deepcopy(removed),
    })
    return revised
