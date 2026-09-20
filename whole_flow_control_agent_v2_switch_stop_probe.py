"""V2 whole-match Relation Flow controller.

Design unit changed from V1:
- keep the same observable axes: money / capacity / public production
- keep the same coarse action mapping: push=.04, maintain=.04, stop=.02, switch=0.0
- replace the scalar average relation score with an axis-wise majority representation

The controller reads one live trajectory only. It never receives seed, paired
results, terminal reward, or future State as runtime control inputs.
"""

import copy
import os
from collections import Counter, deque

import g17_agent as body
from external_economic_lens import evaluate_economic


DAY_CALLS = 24
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
    market = obs.get("market", {}) or {}
    return {
        "day": obs.get("day"),
        "axes": axes,
        "market": {
            "prices": copy.deepcopy(market.get("prices", {})),
            "inventory": copy.deepcopy(market.get("inventory", {})),
        },
    }


def _mode(current, one_day_ago):
    if one_day_ago is None:
        return "maintain", None

    movements = {
        key: current["axes"][key] - one_day_ago["axes"][key]
        for key in current["axes"]
    }
    relation_votes = sum(value >= 0.0 for value in current["axes"].values())
    movement_votes = sum(value >= 0.0 for value in movements.values())

    relation_favorable = relation_votes >= 2
    movement_favorable = movement_votes >= 2

    if relation_favorable and movement_favorable:
        mode = "push"
    elif relation_favorable and not movement_favorable:
        mode = "stop"
    elif not relation_favorable and movement_favorable:
        mode = "maintain"
    else:
        mode = "switch"

    return mode, {
        "axis_movements": movements,
        "relation_favorable_votes": relation_votes,
        "movement_favorable_votes": movement_votes,
    }


def reset_telemetry():
    global _state
    body.reset_telemetry()
    _state = {
        "turn": 0,
        # Intentionally identical to V1 so V2 changes representation only.
        # After warmup this means history[0] is effectively a 25-call gap.
        "history": deque(maxlen=DAY_CALLS + 1),
        "mode_counts": Counter(),
        "magnitude_counts": Counter(),
        "controlled_turns": 0,
        "events": [],
        "family_intervention_count": 0,
    }


def agent(obs):
    if not _state:
        reset_telemetry()
    relation = _relation(obs)
    history = _state["history"]
    one_day_ago = history[0] if len(history) >= DAY_CALLS else None
    mode, flow = _mode(relation, one_day_ago)
    applied_mode = mode
    family_intervention = False
    economic = None
    if _enabled and mode == "switch" and flow is not None:
        economic = evaluate_economic({
            "relation_axes": dict(relation["axes"]),
            "axis_movements": dict(flow["axis_movements"]),
        })
        if economic["judgment"] == "stop":
            applied_mode = "stop"
            family_intervention = True
            _state["family_intervention_count"] += 1
    magnitude = MODE_MAGNITUDE[applied_mode] if _enabled else BASE_MAGNITUDE

    old = os.environ.get("ORIGIN_GATE_MAGNITUDE")
    os.environ["ORIGIN_GATE_MAGNITUDE"] = str(magnitude)
    try:
        action = body.agent(obs)
    finally:
        if old is None:
            os.environ.pop("ORIGIN_GATE_MAGNITUDE", None)
        else:
            os.environ["ORIGIN_GATE_MAGNITUDE"] = old

    applied = magnitude if _enabled else BASE_MAGNITUDE
    _state["mode_counts"][applied_mode if _enabled else "control_off"] += 1
    _state["magnitude_counts"][str(applied)] += 1
    if _enabled and applied != BASE_MAGNITUDE:
        _state["controlled_turns"] += 1

    event = {
        "turn": _state["turn"],
        "day": relation["day"],
        "relation_axes": dict(relation["axes"]),
        "mode": applied_mode if _enabled else "control_off",
        "combat_mode": mode,
        "family_intervention": family_intervention,
        "economic_judgment": economic["judgment"] if economic else None,
        "gate_magnitude": applied,
        "terminal_or_pair_input": False,
    }
    if flow is None:
        event.update({
            "axis_movements": None,
            "relation_favorable_votes": None,
            "movement_favorable_votes": None,
        })
    else:
        event.update({
            "axis_movements": {k: round(v, 8) for k, v in flow["axis_movements"].items()},
            "relation_favorable_votes": flow["relation_favorable_votes"],
            "movement_favorable_votes": flow["movement_favorable_votes"],
        })

    _state["events"].append(event)
    history.append(relation)
    _state["turn"] += 1
    return action


def get_telemetry():
    result = dict(body.get_telemetry())
    result.update({
        "whole_flow_control_enabled": _enabled,
        "whole_flow_version": "v2-vector-majority-switch-stop-family-probe",
        "whole_flow_turns": _state.get("turn", 0),
        "whole_flow_controlled_turns": _state.get("controlled_turns", 0),
        "whole_flow_mode_counts": dict(_state.get("mode_counts", {})),
        "whole_flow_magnitude_counts": dict(_state.get("magnitude_counts", {})),
        "family_probe": "switch_to_stop_v0",
        "family_intervention_count": _state.get("family_intervention_count", 0),
    })
    return result


def get_trace():
    return {
        "whole_flow": [dict(event) for event in _state.get("events", [])],
        "body": body.get_trace(),
    }
