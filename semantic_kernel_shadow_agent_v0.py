from __future__ import annotations

import copy

import whole_flow_control_agent as native
from kaggriculture_production_adapter_v0 import attach_emitted_action, observe_semantics


_state = {"turn": 0, "trace": []}


def set_control_enabled(enabled):
    native.set_control_enabled(enabled)


def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)


def reset_telemetry():
    global _state
    native.reset_telemetry()
    _state = {"turn": 0, "trace": []}


def agent(obs):
    record = observe_semantics(obs)
    action = native.agent(obs)
    record = attach_emitted_action(record, action)
    record["turn"] = _state["turn"]
    record["day"] = obs.get("day")
    _state["trace"].append(record)
    _state["turn"] += 1
    return action


def get_telemetry():
    result = dict(native.get_telemetry())
    result["semantic_shadow_turns"] = _state.get("turn", 0)
    return result


def get_trace():
    return {
        "semantic_shadow": copy.deepcopy(_state.get("trace", [])),
        "native": native.get_trace(),
    }
