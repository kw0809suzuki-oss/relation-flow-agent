"""Minimal LAND terminal-gate battle probe.

Intervention:
- suppress the first native market action BUY_LAND
- once per match
- preserve every other native action

Purpose:
Fill LAND Candidate Bundle Terminal gate.
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


def _is_buy_land(action):
    return (
        isinstance(action, (list, tuple))
        and len(action) >= 1
        and action[0] == "BUY_LAND"
    )


def agent(obs):
    global _activated
    actions = native.agent(obs)
    if _activated or not isinstance(actions, dict):
        return actions

    market = list(actions.get("market", []) or [])
    if not any(_is_buy_land(a) for a in market):
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if not _is_buy_land(a)]
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
