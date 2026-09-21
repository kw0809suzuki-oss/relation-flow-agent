"""Marginal HIRE Suppression v0.

Keep the current G17 policy intact except for expensive marginal daily HIREs.
A HIRE whose Fibonacci marginal cost is >= 34 is removed from the final market
bundle. This is a Battle candidate, not an adopted rule.
"""

import copy
import g17_agent as base

THRESHOLD = 34
_stats = {"suppressed_hires": 0, "suppressed_costs": {}, "turns_changed": 0}


def fib_hire_cost(n):
    a, b = 1, 1
    for _ in range(int(n)):
        a, b = b, a + b
    return a


def reset_telemetry():
    global _stats
    base.reset_telemetry()
    _stats = {"suppressed_hires": 0, "suppressed_costs": {}, "turns_changed": 0}


def set_probe_enabled(enabled):
    return base.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    return base.set_attribution_enabled(enabled)


def get_telemetry():
    out = dict(base.get_telemetry())
    out.update({
        "marginal_hire_threshold": THRESHOLD,
        "suppressed_hires": _stats["suppressed_hires"],
        "suppressed_costs": dict(_stats["suppressed_costs"]),
        "marginal_hire_turns_changed": _stats["turns_changed"],
    })
    return out


def get_trace():
    return base.get_trace()


def agent(obs):
    action = base.agent(obs)
    market = list(action.get("market", []))
    hires_today = int(obs["farms"][obs["player"]].get("hires_today", 0) or 0)
    hire_index = 0
    changed = False
    filtered = []

    for order in market:
        if order and order[0] == "HIRE":
            cost = fib_hire_cost(hires_today + hire_index)
            hire_index += 1
            if cost >= THRESHOLD:
                _stats["suppressed_hires"] += 1
                key = str(cost)
                _stats["suppressed_costs"][key] = _stats["suppressed_costs"].get(key, 0) + 1
                changed = True
                continue
        filtered.append(order)

    if changed:
        _stats["turns_changed"] += 1
        action = copy.deepcopy(action)
        action["market"] = filtered
    return action
