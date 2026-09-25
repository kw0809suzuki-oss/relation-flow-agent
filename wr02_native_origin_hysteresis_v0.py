"""WR-02 + Native Origin Hysteresis v0.

Minimal continuity intervention:
- Keep Current WR-02 unchanged.
- Use Current's own native Origin decision only.
- A non-ENDGAME Origin switch must be requested on two consecutive turns before
  the effective Origin changes.
- ENDGAME remains immediate at the existing finite-horizon boundary.
- No external role, teacher, opponent policy copy, fixed sequence, or target
  rewrite is introduced.
"""
from dataclasses import replace

import strong_origin
import wr02_same_tile_plant_deconfliction_v0 as wr02

_state = {}


def reset_telemetry():
    global _state
    wr02.reset_telemetry()
    _state = {
        "turns": 0,
        "native_switch_requests": 0,
        "delayed_switch_turns": 0,
        "confirmed_switches": 0,
        "effective_origin": None,
        "pending_origin": None,
        "events": [],
    }


def _choose_with_hysteresis(original, field, base_prices):
    native = original(field, base_prices)
    effective = _state.get("effective_origin")
    pending = _state.get("pending_origin")

    if effective is None:
        _state["effective_origin"] = native.origin
        _state["pending_origin"] = None
        return native

    if native.origin == "ENDGAME":
        if effective != "ENDGAME":
            _state["confirmed_switches"] += 1
            _state["events"].append({
                "day": int(field.day),
                "native": native.origin,
                "from": effective,
                "to": "ENDGAME",
                "mode": "immediate_endgame",
            })
        _state["effective_origin"] = "ENDGAME"
        _state["pending_origin"] = None
        return native

    if native.origin == effective:
        _state["pending_origin"] = None
        return native

    _state["native_switch_requests"] += 1

    if pending == native.origin:
        old = effective
        _state["effective_origin"] = native.origin
        _state["pending_origin"] = None
        _state["confirmed_switches"] += 1
        _state["events"].append({
            "day": int(field.day),
            "native": native.origin,
            "from": old,
            "to": native.origin,
            "mode": "confirmed",
        })
        return native

    _state["pending_origin"] = native.origin
    _state["delayed_switch_turns"] += 1
    _state["events"].append({
        "day": int(field.day),
        "native": native.origin,
        "effective": effective,
        "mode": "delayed_once",
    })
    return replace(native, origin=effective, reason=native.reason + " | native-origin hysteresis hold")


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()

    original = strong_origin.choose_x_origin

    def wrapped(field, base_prices):
        return _choose_with_hysteresis(original, field, base_prices)

    strong_origin.choose_x_origin = wrapped
    try:
        action = wr02.agent(obs)
        _state["turns"] += 1
        return action
    finally:
        strong_origin.choose_x_origin = original


def get_telemetry():
    out = dict(wr02.get_telemetry())
    out.update({
        "native_origin_hysteresis": True,
        **_state,
    })
    return out
