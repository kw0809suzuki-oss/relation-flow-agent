"""Observation-only whole-flow recorder for Relation Flow Pattern Mining v1.

This module does not alter actions. It records a broad, result-blind description
of the live trajectory before terminal outcome is attached by the runner.
"""

import copy
from collections import Counter

import g17_agent as body

_state = {}


def reset():
    global _state
    body.set_probe_enabled(True)
    body.set_attribution_enabled(True)
    body.reset_telemetry()
    _state = {"turn": 0, "last_day": None, "day_snapshots": [], "actions": []}


def _inventory(private):
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []
    keys = set(shed)
    for inv in inventories:
        keys.update(inv)
    return {k: shed.get(k, 0) + sum(inv.get(k, 0) for inv in inventories) for k in sorted(keys)}


def _farm_public(farm):
    animals = Counter()
    active_tiles = 0
    planted_tiles = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile in (None, "LOCKED"):
                continue
            active_tiles += 1
            if isinstance(tile, dict):
                animal = tile.get("animal")
                if animal:
                    animals[str(animal)] += 1
                if tile.get("crop") or tile.get("plant"):
                    planted_tiles += 1
    return {
        "money": farm.get("money", 0),
        "hands": len(farm.get("hands", []) or []),
        "unlocked_quadrants": len(farm.get("unlocked_quadrants", []) or []),
        "active_tiles": active_tiles,
        "planted_tiles": planted_tiles,
        "animals": dict(animals),
    }


def _snapshot(obs):
    player = int(obs["player"])
    farms = obs["farms"]
    market = obs.get("market", {}) or {}
    return {
        "turn": _state["turn"],
        "day": obs.get("day"),
        "self": _farm_public(farms[player]),
        "opponent": _farm_public(farms[1 - player]),
        "self_private_inventory": _inventory(obs.get("private", {}) or {}),
        "market": {
            "prices": copy.deepcopy(market.get("prices", {}) or {}),
            "inventory": copy.deepcopy(market.get("inventory", {}) or {}),
        },
    }


def agent(obs):
    if not _state:
        reset()
    snap = _snapshot(obs)
    # Keep the last observation seen for each day. This gives a compact whole-match
    # trajectory without choosing patterns from terminal results.
    day = snap["day"]
    if _state["day_snapshots"] and _state["day_snapshots"][-1]["day"] == day:
        _state["day_snapshots"][-1] = snap
    else:
        _state["day_snapshots"].append(snap)
    action = body.agent(obs)
    _state["actions"].append(copy.deepcopy(action))
    _state["turn"] += 1
    return action


def get_trace():
    return {
        "day_snapshots": copy.deepcopy(_state.get("day_snapshots", [])),
        "actions": copy.deepcopy(_state.get("actions", [])),
        "body_telemetry": copy.deepcopy(body.get_telemetry()),
    }
