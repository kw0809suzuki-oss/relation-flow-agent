"""Investment Deadline Coordinate v0.

Baseline strategy:
- Current Combat Model uses a coarse Day14 closure for all new expansion purchases.

Candidate coordinate:
- LAND: keep the existing Day14 closure because a recovery horizon is unresolved.
- SEED: after Day14, allow only while remaining days exceed crop FIRST_YIELD + 1.
- COW: after Day14, allow only while remaining days >= 8 (existing grounded recovery test horizon).
- HIRE / HARVEST / SELL / unit actions remain unchanged.

This replaces only the fixed Day14 SEED/COW cutoff with recovery-deadline logic.
No LAND payback estimate is invented.
"""

import copy

import g17_agent as native
from strong_origin import FIRST_YIELD

TERMINAL_DAY = 30
LAND_CLOSURE_DAY = 14
COW_RECOVERY_DAYS = 8

_state = {}

def reset_experiment():
    global _state
    _state = {
        "considered": 0,
        "allowed_after_d14": 0,
        "removed_by_deadline": 0,
        "removed_land_d14": 0,
        "events": [],
    }
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def _op(a):
    return a[0] if isinstance(a,(list,tuple)) and a else None

def _is_land(a):
    return _op(a) == "BUY_LAND"

def _is_seed(a):
    return _op(a) == "BUY_SEED"

def _seed_crop(a):
    return a[1] if isinstance(a,(list,tuple)) and len(a)>1 else None

def _is_cow(a):
    return (
        _op(a) == "BUY_ANIMAL" and len(a)>1 and a[1] == "COW"
    ) or (
        _op(a) == "BUY_PRODUCT" and len(a)>1 and a[1] == "COW"
    )

def _decision(a, day):
    """Return (keep, reason, horizon)."""
    if day < LAND_CLOSURE_DAY:
        return True, "before_d14", None

    remaining = TERMINAL_DAY - day

    if _is_land(a):
        return False, "land_d14_unresolved_payback", None

    if _is_seed(a):
        crop = _seed_crop(a)
        if crop not in FIRST_YIELD:
            return True, "seed_unknown_preserve", None
        horizon = int(FIRST_YIELD[crop]) + 1
        return remaining > horizon, "seed_recovery_deadline", horizon

    if _is_cow(a):
        return remaining >= COW_RECOVERY_DAYS, "cow_recovery_deadline", COW_RECOVERY_DAYS

    return True, "non_target", None

def agent(obs):
    if not _state:
        reset_experiment()

    actions = native.agent(obs)
    if not isinstance(actions,dict):
        return actions

    day = int(obs.get("day",0) or 0)
    market = list(actions.get("market",[]) or [])
    revised_market = []
    changes = []

    for a in market:
        target = _is_land(a) or _is_seed(a) or _is_cow(a)
        if not target:
            revised_market.append(a)
            continue

        _state["considered"] += 1
        keep, reason, horizon = _decision(a, day)

        if keep:
            revised_market.append(a)
            if day >= LAND_CLOSURE_DAY:
                _state["allowed_after_d14"] += 1
                changes.append({
                    "kind":"allow",
                    "day":day,
                    "action":copy.deepcopy(a),
                    "reason":reason,
                    "horizon":horizon,
                    "remaining_days":TERMINAL_DAY-day,
                })
        else:
            if reason == "land_d14_unresolved_payback":
                _state["removed_land_d14"] += 1
            else:
                _state["removed_by_deadline"] += 1
            changes.append({
                "kind":"remove",
                "day":day,
                "action":copy.deepcopy(a),
                "reason":reason,
                "horizon":horizon,
                "remaining_days":TERMINAL_DAY-day,
            })

    if not changes:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = revised_market
    _state["events"].extend(changes)
    return revised

def get_experiment_telemetry():
    return copy.deepcopy(_state)

def get_trace():
    return native.get_trace()
