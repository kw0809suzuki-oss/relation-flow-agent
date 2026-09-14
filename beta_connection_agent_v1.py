"""Connection experiment v1: connect confirmed beta-stop to next-day action strength.

Observation side is frozen: beta-stop means self active_tiles and self COW both
change direction up -> flat on completed daily snapshots.
Connection only: after beta-stop is confirmed, use ORIGIN_GATE_MAGNITUDE=0.02
for the following game day; otherwise keep baseline 0.04.
No seed, terminal, paired result, or future state is used at runtime.
"""

import copy
import os
from collections import Counter

import g17_agent as body

BASE_MAGNITUDE = 0.04
BETA_MAGNITUDE = 0.02
_enabled = True
_state = {}


def set_control_enabled(enabled):
    global _enabled
    _enabled = bool(enabled)


def set_probe_enabled(enabled):
    body.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    body.set_attribution_enabled(enabled)


def _farm_public(farm):
    active = 0
    cows = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile in (None, "LOCKED"):
                continue
            active += 1
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                cows += 1
    return {"active_tiles": active, "cows": cows}


def _snapshot(obs):
    player = int(obs["player"])
    return {
        "day": obs.get("day"),
        "self": _farm_public(obs["farms"][player]),
    }


def _direction(a, b):
    return "up" if b > a else "down" if b < a else "flat"


def _beta_stop(finalized):
    if len(finalized) < 3:
        return False
    a, b, c = finalized[-3:]
    active_prev = _direction(a["self"]["active_tiles"], b["self"]["active_tiles"])
    active_now = _direction(b["self"]["active_tiles"], c["self"]["active_tiles"])
    cow_prev = _direction(a["self"]["cows"], b["self"]["cows"])
    cow_now = _direction(b["self"]["cows"], c["self"]["cows"])
    return active_prev == "up" and active_now == "flat" and cow_prev == "up" and cow_now == "flat"


def reset_telemetry():
    global _state
    body.reset_telemetry()
    _state = {
        "turn": 0,
        "current_day": None,
        "current_snapshot": None,
        "finalized_days": [],
        "beta_control_day": None,
        "beta_events": [],
        "magnitude_counts": Counter(),
        "controlled_turns": 0,
        "events": [],
    }


def agent(obs):
    if not _state:
        reset_telemetry()

    snap = _snapshot(obs)
    day = snap["day"]

    if _state["current_day"] is None:
        _state["current_day"] = day
        _state["current_snapshot"] = snap
    elif day == _state["current_day"]:
        _state["current_snapshot"] = snap
    else:
        # Previous day's last observation is now finalized and can be used causally.
        _state["finalized_days"].append(copy.deepcopy(_state["current_snapshot"]))
        if _beta_stop(_state["finalized_days"]):
            _state["beta_control_day"] = day
            _state["beta_events"].append({
                "confirmed_after_day": _state["finalized_days"][-1]["day"],
                "applied_on_day": day,
            })
        else:
            _state["beta_control_day"] = None
        _state["current_day"] = day
        _state["current_snapshot"] = snap

    beta_active = _enabled and day == _state.get("beta_control_day")
    magnitude = BETA_MAGNITUDE if beta_active else BASE_MAGNITUDE

    old = os.environ.get("ORIGIN_GATE_MAGNITUDE")
    os.environ["ORIGIN_GATE_MAGNITUDE"] = str(magnitude)
    try:
        action = body.agent(obs)
    finally:
        if old is None:
            os.environ.pop("ORIGIN_GATE_MAGNITUDE", None)
        else:
            os.environ["ORIGIN_GATE_MAGNITUDE"] = old

    _state["magnitude_counts"][str(magnitude)] += 1
    if beta_active:
        _state["controlled_turns"] += 1
    _state["events"].append({
        "turn": _state["turn"],
        "day": day,
        "beta_control_active": beta_active,
        "gate_magnitude": magnitude,
        "terminal_or_pair_input": False,
    })
    _state["turn"] += 1
    return action


def get_telemetry():
    result = dict(body.get_telemetry())
    result.update({
        "connection_version": "beta-stop-next-day-v1",
        "connection_enabled": _enabled,
        "beta_event_count": len(_state.get("beta_events", [])),
        "beta_events": copy.deepcopy(_state.get("beta_events", [])),
        "controlled_turns": _state.get("controlled_turns", 0),
        "magnitude_counts": dict(_state.get("magnitude_counts", {})),
    })
    return result


def get_trace():
    return copy.deepcopy(_state.get("events", []))
