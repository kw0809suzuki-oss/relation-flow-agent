"""Payback Closure Candidate v0.

Coarse battle candidate derived from current external evidence:
- when remaining horizon <= 14 days, suppress new expansion purchases
- preserve every other native G17 action

This is intentionally coarse. It operationalizes the observed closure/payback
boundary without adding a payback predictor yet.
"""
import copy
import g17_agent as native

TERMINAL_DAY = 30
MIN_RECOVERY_HORIZON = 14

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
    return op == "BUY_PRODUCT" and len(action) > 1 and action[1] == "COW"


def agent(obs):
    actions = native.agent(obs)
    if not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    remaining = TERMINAL_DAY - day

    if remaining > MIN_RECOVERY_HORIZON:
        return actions

    market = list(actions.get("market", []) or [])
    removed = [a for a in market if _is_expansion_purchase(a)]
    if not removed:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if not _is_expansion_purchase(a)]
    _activations.append({
        "day": day,
        "remaining_horizon": remaining,
        "removed": copy.deepcopy(removed),
    })
    return revised


def get_activations():
    return copy.deepcopy(_activations)


def get_trace():
    return native.get_trace()
