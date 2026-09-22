"""Time-aware Liquidation Candidate v0.

Baseline:
- Current Combat Model.
- Adopted Day14 expansion closure remains unchanged.
- HIRE remains preserved.
- Native SELL behavior remains unchanged.

Candidate:
- Only when a unit is already standing on a harvestable WHEAT/MELON plant,
  and waiting for native max-yield age would consume the remaining season,
  harvest now instead of waiting.

No price predictor, no extra reserve rule, no SELL override, no rescue condition.
"""

import copy

import whole_flow_control_agent as native
from strong_origin import MAX_YIELD_DAY

TERMINAL_DAY = 30
_state = {}

def reset_experiment():
    global _state
    _state = {
        "eligible": 0,
        "overrides": 0,
        "events": [],
    }
    native.reset_telemetry()

def set_probe_enabled(enabled):
    native.set_probe_enabled(enabled)

def set_attribution_enabled(enabled):
    native.set_attribution_enabled(enabled)

def _deadline_harvest(tile, day):
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return False, None
    crop = tile.get("crop")
    if crop not in ("WHEAT", "MELON"):
        return False, None
    yield_units = float(tile.get("yield_units", 0) or 0)
    if yield_units <= 0:
        return False, None
    planted_day = int(tile.get("planted_day", day) or day)
    age = day - planted_day
    max_age = MAX_YIELD_DAY.get(crop)
    if max_age is None or age >= max_age:
        return False, None
    wait_days = max_age - age
    remaining_days = TERMINAL_DAY - day
    hit = wait_days >= remaining_days
    return hit, {
        "crop": crop,
        "age": age,
        "max_age": max_age,
        "wait_days": wait_days,
        "remaining_days": remaining_days,
        "yield_units": yield_units,
    }

def agent(obs):
    if not _state:
        reset_experiment()

    actions = native.agent(obs)
    if not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    p = int(obs["player"])
    me = obs["farms"][p]
    tiles = me.get("tiles", []) or []
    revised = copy.deepcopy(actions)
    changed = []

    def inspect_unit(label, pos, current_action):
        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            return current_action
        x, y = pos
        if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[y]):
            return current_action
        hit, reason = _deadline_harvest(tiles[y][x], day)
        if not hit:
            return current_action
        _state["eligible"] += 1
        if current_action != ["HARVEST"]:
            _state["overrides"] += 1
            changed.append({
                "unit": label,
                "x": x,
                "y": y,
                "before": copy.deepcopy(current_action),
                "after": ["HARVEST"],
                "reason": reason,
            })
            return ["HARVEST"]
        return current_action

    revised["farmer"] = inspect_unit("farmer", me.get("farmer"), revised.get("farmer"))

    hand_actions = list(revised.get("hands", []) or [])
    hands = list(me.get("hands", []) or [])
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])
    for i, pos in enumerate(hands):
        hand_actions[i] = inspect_unit(f"hand_{i}", pos, hand_actions[i])
    revised["hands"] = hand_actions

    if changed:
        _state["events"].append({
            "day": day,
            "money": me.get("money"),
            "changes": changed,
        })

    return revised

def get_experiment_telemetry():
    return copy.deepcopy(_state)

def get_trace():
    return native.get_trace()
