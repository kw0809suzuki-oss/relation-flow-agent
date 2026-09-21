"""Whole-match Relation Flow controller over the unchanged G17 agent.

The controller reads one live trajectory only. It never sees seed, paired
results, terminal reward, or future State. Native Origin keeps direction;
Relation Flow can only retain, soften, or remove the existing gate modulation.

Adopted combat rule:
- From day 14 onward, suppress new late-expansion purchases:
  BUY_LAND, BUY_SEED, BUY_ANIMAL, BUY_PRODUCT COW.
- HIRE, HARVEST, unit actions, and other market actions are unchanged.
"""

import copy
import os
from collections import Counter, deque

import g17_agent as body


DAY_CALLS = 24
ADOPTED_D14_START_DAY = 14
BASE_MAGNITUDE = 0.04
MODE_MAGNITUDE = {
    "push": 0.04,
    "maintain": 0.04,
    "stop": 0.02,
    "switch": 0.0,
}

_enabled = True
_state = {}


def set_control_enabled(enabled):
    global _enabled
    _enabled = bool(enabled)


def set_probe_enabled(enabled):
    body.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    body.set_attribution_enabled(enabled)


def _is_adopted_d14_expansion(order):
    if not isinstance(order, (list, tuple)) or not order:
        return False
    op = order[0]
    if op in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(order) > 1 and order[1] == "COW"


def _apply_adopted_d14(obs, action):
    if not isinstance(action, dict):
        return action, []
    day = int(obs.get("day", 0) or 0)
    if day < ADOPTED_D14_START_DAY:
        return action, []

    market = list(action.get("market", []) or [])
    removed = [copy.deepcopy(order) for order in market if _is_adopted_d14_expansion(order)]
    if not removed:
        return action, []

    revised = copy.deepcopy(action)
    revised["market"] = [order for order in market if not _is_adopted_d14_expansion(order)]
    return revised, removed


def _clip(value):
    return max(-1.0, min(1.0, float(value)))


def _ratio(left, right):
    return _clip((float(left) - float(right)) / max(1.0, abs(float(left)) + abs(float(right))))


def _public_production(farm):
    active = animals = 0
    for row in farm.get("tiles", []):
        for tile in row:
            if tile == "LOCKED" or tile is None:
                continue
            active += 1
            if isinstance(tile, dict) and tile.get("animal"):
                animals += 1
    return active + animals


def _relation(obs):
    player = int(obs["player"])
    me = obs["farms"][player]
    opponent = obs["farms"][1 - player]
    self_capacity = 1 + len(me.get("hands", [])) + len(me.get("unlocked_quadrants", []))
    opponent_capacity = 1 + len(opponent.get("hands", [])) + len(opponent.get("unlocked_quadrants", []))
    axes = {
        "money": _ratio(me.get("money", 0), opponent.get("money", 0)),
        "capacity": _ratio(self_capacity, opponent_capacity),
        "production": _ratio(_public_production(me), _public_production(opponent)),
    }
    score = sum(axes.values()) / len(axes)
    market = obs.get("market", {}) or {}
    return {
        "day": obs.get("day"),
        "axes": axes,
        "score": score,
        "market": {
            "prices": copy.deepcopy(market.get("prices", {})),
            "inventory": copy.deepcopy(market.get("inventory", {})),
        },
    }


def _mode(current, one_day_ago):
    if one_day_ago is None:
        return "maintain", None
    movement = current["score"] - one_day_ago["score"]
    if current["score"] >= 0.0 and movement >= 0.0:
        return "push", movement
    if current["score"] >= 0.0 and movement < 0.0:
        return "stop", movement
    if current["score"] < 0.0 and movement >= 0.0:
        return "maintain", movement
    return "switch", movement


def reset_telemetry():
    global _state
    body.reset_telemetry()
    _state = {
        "turn": 0,
        "history": deque(maxlen=DAY_CALLS + 1),
        "mode_counts": Counter(),
        "magnitude_counts": Counter(),
        "controlled_turns": 0,
        "adopted_d14_changed_turns": 0,
        "adopted_d14_removed_orders": 0,
        "adopted_d14_removed_by_op": Counter(),
        "events": [],
    }


def agent(obs):
    if not _state:
        reset_telemetry()
    relation = _relation(obs)
    history = _state["history"]
    one_day_ago = history[0] if len(history) >= DAY_CALLS else None
    mode, movement = _mode(relation, one_day_ago)
    magnitude = MODE_MAGNITUDE[mode] if _enabled else BASE_MAGNITUDE

    old = os.environ.get("ORIGIN_GATE_MAGNITUDE")
    os.environ["ORIGIN_GATE_MAGNITUDE"] = str(magnitude)
    try:
        action = body.agent(obs)
    finally:
        if old is None:
            os.environ.pop("ORIGIN_GATE_MAGNITUDE", None)
        else:
            os.environ["ORIGIN_GATE_MAGNITUDE"] = old

    action, d14_removed = _apply_adopted_d14(obs, action)

    if d14_removed:
        _state["adopted_d14_changed_turns"] += 1
        _state["adopted_d14_removed_orders"] += len(d14_removed)
        for order in d14_removed:
            op = order[0]
            key = "BUY_PRODUCT_COW" if op == "BUY_PRODUCT" else op
            _state["adopted_d14_removed_by_op"][key] += 1

    applied = magnitude if _enabled else BASE_MAGNITUDE
    _state["mode_counts"][mode if _enabled else "control_off"] += 1
    _state["magnitude_counts"][str(applied)] += 1
    if _enabled and applied != BASE_MAGNITUDE:
        _state["controlled_turns"] += 1
    _state["events"].append({
        "turn": _state["turn"],
        "day": relation["day"],
        "relation_axes": dict(relation["axes"]),
        "relation_score": round(relation["score"], 8),
        "one_day_movement": None if movement is None else round(movement, 8),
        "mode": mode if _enabled else "control_off",
        "gate_magnitude": applied,
        "adopted_d14_applied": bool(d14_removed),
        "adopted_d14_removed": d14_removed,
        "terminal_or_pair_input": False,
    })
    history.append(relation)
    _state["turn"] += 1
    return action


def get_telemetry():
    result = dict(body.get_telemetry())
    result.update({
        "whole_flow_control_enabled": _enabled,
        "whole_flow_turns": _state.get("turn", 0),
        "whole_flow_controlled_turns": _state.get("controlled_turns", 0),
        "whole_flow_mode_counts": dict(_state.get("mode_counts", {})),
        "whole_flow_magnitude_counts": dict(_state.get("magnitude_counts", {})),
        "adopted_d14_enabled": True,
        "adopted_d14_start_day": ADOPTED_D14_START_DAY,
        "adopted_d14_changed_turns": _state.get("adopted_d14_changed_turns", 0),
        "adopted_d14_removed_orders": _state.get("adopted_d14_removed_orders", 0),
        "adopted_d14_removed_by_op": dict(_state.get("adopted_d14_removed_by_op", {})),
    })
    return result


def get_trace():
    return {
        "whole_flow": [dict(event) for event in _state.get("events", [])],
        "body": body.get_trace(),
    }
