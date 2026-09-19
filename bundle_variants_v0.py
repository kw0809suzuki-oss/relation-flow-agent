"""Bundle closure/timing variants v0 over frozen G17 Current.

All variants post-process only the market bundle. They do not alter G17 internals.
These are experimental biases, not adopted policies.
"""
import copy
import g17_agent as native

TERMINAL_DAY = 30
_active_variant = "M0"
_activations = []

def set_variant(name):
    global _active_variant
    _active_variant = name

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

def _is_seed(a):
    return _op(a) == "BUY_SEED"

def _is_cow(a):
    return (
        _op(a) == "BUY_ANIMAL"
        and len(a) > 1 and a[1] == "COW"
    ) or (
        _op(a) == "BUY_PRODUCT"
        and len(a) > 1 and a[1] == "COW"
    )

def _is_land(a):
    return _op(a) == "BUY_LAND"

def _is_expansion(a):
    return _is_seed(a) or _is_cow(a) or _is_land(a)

def _qty(a):
    try:
        return max(1, int(a[2]))
    except Exception:
        return 1

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

def _keep_m2(a, obs):
    # Early Closure: from Day20, stop all new expansion purchases.
    return not (int(obs.get("day", 0) or 0) >= 20 and _is_expansion(a))

def _keep_m3(a, obs):
    # Late Closure: same bias, but only from Day26.
    return not (int(obs.get("day", 0) or 0) >= 26 and _is_expansion(a))

def _keep_m4(a, obs):
    # Time-weighted cash reserve:
    # required reserve fraction rises linearly from 0 at Day0 to 1 at terminal.
    if not _is_expansion(a):
        return True
    day = int(obs.get("day", 0) or 0)
    me = obs["farms"][obs["player"]]
    money = float(me.get("money", 0) or 0)
    reserve = money * min(1.0, max(0.0, day / TERMINAL_DAY))
    return (money - _cost(a, obs)) >= reserve

def _keep_m6(a, obs):
    # Recovery-first: only apply where first-return timing is already grounded.
    # SEED needs >=4 days; COW needs >=8 days. LAND remains untouched because
    # its return horizon is explicitly unresolved.
    if not _is_expansion(a):
        return True
    remaining = TERMINAL_DAY - int(obs.get("day", 0) or 0)
    if _is_seed(a):
        return remaining >= 4
    if _is_cow(a):
        return remaining >= 8
    return True

def _keep_m7(a, obs):
    # Explicit staged switch:
    # Day20+: stop slow expansion (LAND/COW).
    # Day26+: stop all new expansion including SEED.
    if not _is_expansion(a):
        return True
    day = int(obs.get("day", 0) or 0)
    if day >= 26:
        return False
    if day >= 20 and (_is_land(a) or _is_cow(a)):
        return False
    return True

_KEEP = {
    "M0": lambda a, obs: True,
    "M2": _keep_m2,
    "M3": _keep_m3,
    "M4": _keep_m4,
    "M6": _keep_m6,
    "M7": _keep_m7,
}

def agent(obs):
    actions = native.agent(obs)
    if _active_variant == "M0" or not isinstance(actions, dict):
        return actions

    keep = _KEEP[_active_variant]
    market = list(actions.get("market", []) or [])
    removed = [a for a in market if not keep(a, obs)]
    if not removed:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if keep(a, obs)]
    _activations.append({
        "variant": _active_variant,
        "day": int(obs.get("day", 0) or 0),
        "removed": copy.deepcopy(removed),
        "before_market": copy.deepcopy(market),
        "after_market": copy.deepcopy(revised["market"]),
    })
    return revised
