"""Closure/Timing bundle variants v1 over frozen G17 Current.

Experimental biases only. All variants post-process the market bundle in one place.
No variant is an adopted policy.
"""
import copy
import g17_agent as native

TERMINAL_DAY = 30
_active = "M3"
_activations = []

def set_variant(name):
    global _active
    _active = name

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

def _qty(a):
    try:
        return max(1, int(a[2]))
    except Exception:
        return 1

def _is_seed(a):
    return _op(a) == "BUY_SEED"

def _is_cow(a):
    return (
        _op(a) == "BUY_ANIMAL" and len(a) > 1 and a[1] == "COW"
    ) or (
        _op(a) == "BUY_PRODUCT" and len(a) > 1 and a[1] == "COW"
    )

def _is_land(a):
    return _op(a) == "BUY_LAND"

def _is_expansion(a):
    return _is_seed(a) or _is_cow(a) or _is_land(a)

def _land_cost(obs):
    me = obs["farms"][obs["player"]]
    n = max(1, len(me.get("unlocked_quadrants", [])))
    return {1: 1000.0, 2: 2000.0, 3: 4000.0}.get(n, 10**9)

def _cost(a, obs):
    if _is_seed(a):
        return 10.0 * _qty(a)
    if _is_cow(a):
        return 400.0 * _qty(a)
    if _is_land(a):
        return _land_cost(obs)
    return 0.0

def _keep_m3(a, obs):
    # Late Closure test knob: Day26+ stop all new expansion.
    return not (int(obs.get("day", 0) or 0) >= 26 and _is_expansion(a))

def _keep_m4(a, obs):
    # Time-weighted cash reserve test:
    # reserve share rises linearly with elapsed season fraction.
    if not _is_expansion(a):
        return True
    day = int(obs.get("day", 0) or 0)
    money = float(obs["farms"][obs["player"]].get("money", 0) or 0)
    reserve = money * min(1.0, max(0.0, day / TERMINAL_DAY))
    return (money - _cost(a, obs)) >= reserve

def _keep_m6(a, obs):
    # Recovery-first using only currently grounded first-return horizons.
    if not _is_expansion(a):
        return True
    remaining = TERMINAL_DAY - int(obs.get("day", 0) or 0)
    if _is_seed(a):
        return remaining >= 4
    if _is_cow(a):
        return remaining >= 8
    # LAND return horizon unresolved: do not invent it here.
    return True

def _keep_m7(a, obs):
    # Explicit staged switch test knob.
    # Day20+: stop slower LAND/COW expansion.
    # Day26+: stop all new expansion.
    if not _is_expansion(a):
        return True
    day = int(obs.get("day", 0) or 0)
    if day >= 26:
        return False
    if day >= 20 and (_is_land(a) or _is_cow(a)):
        return False
    return True

_KEEP = {"M3": _keep_m3, "M4": _keep_m4, "M6": _keep_m6, "M7": _keep_m7}

def agent(obs):
    actions = native.agent(obs)
    if not isinstance(actions, dict):
        return actions
    keep = _KEEP[_active]
    market = list(actions.get("market", []) or [])
    removed = [a for a in market if not keep(a, obs)]
    if not removed:
        return actions
    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if keep(a, obs)]
    _activations.append({
        "variant": _active,
        "day": int(obs.get("day", 0) or 0),
        "removed": copy.deepcopy(removed),
    })
    return revised
