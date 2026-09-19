"""Minimal persistent-state battle probe.

Intervention:
- suppress the first native market action BUY_ANIMAL COW 1
- once per match
- preserve every other native action

Purpose:
Test whether changing a persistent cows state produces terminal-relevant effects.
This is an intervention probe, not an adopted Combat Rule.
"""
import copy

import whole_flow_control_agent as native

_activated = False
_activations = []


def reset_experiment():
    global _activated, _activations
    _activated = False
    _activations = []
    native.reset_telemetry()


def set_control_enabled(enabled):
    native.set_control_enabled(enabled)


def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)


def _is_cow1(action):
    return (
        isinstance(action, (list, tuple))
        and len(action) >= 3
        and action[0] in ("BUY_ANIMAL", "BUY_PRODUCT")
        and action[1] == "COW"
        and int(action[2]) == 1
    )


def agent(obs):
    global _activated
    actions = native.agent(obs)
    if _activated or not isinstance(actions, dict):
        return actions

    market = list(actions.get("market", []) or [])
    hits = [a for a in market if _is_cow1(a)]
    if not hits:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if not _is_cow1(a)]
    _activated = True
    _activations.append({
        "day": obs.get("day"),
        "before_market": copy.deepcopy(market),
        "after_market": copy.deepcopy(revised["market"]),
        "target_removed": True,
    })
    return revised


def get_activations():
    return copy.deepcopy(_activations)


def get_trace():
    return native.get_trace()
