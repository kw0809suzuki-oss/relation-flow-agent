"""Closure -> Cash/Recovery Switch Candidate v0.

Main-line connection test only.

Base is the frozen 14-day Closure candidate:
    remaining horizon <= 14 -> suppress new expansion purchases

After Closure is active, add only a coarse Switch direction:
- suppress HIRE (avoid adding fresh labor capacity)
- if a unit is already standing on a plant with harvestable yield, harvest now
  rather than waiting for a later max-yield timing

No payback predictor. No threshold tuning. No extra rescue conditions.
"""
import copy

import payback_closure_candidate_v0 as closure

TERMINAL_DAY = 30
SWITCH_HORIZON = 14

_switch_events = []


def reset_experiment():
    global _switch_events
    _switch_events = []
    closure.reset_experiment()


def set_probe_enabled(enabled):
    closure.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    closure.set_attribution_enabled(enabled)


def _harvestable_here(tile):
    return (
        isinstance(tile, dict)
        and tile.get("kind") == "PLANT"
        and float(tile.get("yield_units", 0) or 0) > 0
    )


def agent(obs):
    actions = closure.agent(obs)
    if not isinstance(actions, dict):
        return actions

    day = int(obs.get("day", 0) or 0)
    remaining = TERMINAL_DAY - day
    if remaining > SWITCH_HORIZON:
        return actions

    revised = copy.deepcopy(actions)
    changed = []

    market = list(revised.get("market", []) or [])
    kept_market = [a for a in market if not (isinstance(a, (list, tuple)) and a and a[0] == "HIRE")]
    if len(kept_market) != len(market):
        changed.append({"kind": "suppress_hire", "count": len(market) - len(kept_market)})
        revised["market"] = kept_market

    player = obs["player"]
    me = obs["farms"][player]
    tiles = me.get("tiles", []) or []

    farmer = me.get("farmer")
    if farmer and len(farmer) == 2:
        x, y = farmer
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and _harvestable_here(tiles[y][x]):
            if revised.get("farmer") != ["HARVEST"]:
                revised["farmer"] = ["HARVEST"]
                changed.append({"kind": "early_harvest", "unit": "farmer", "x": x, "y": y})

    hands_pos = me.get("hands", []) or []
    hand_actions = list(revised.get("hands", []) or [])
    for i, pos in enumerate(hands_pos):
        if i >= len(hand_actions) or not pos or len(pos) != 2:
            continue
        x, y = pos
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) and _harvestable_here(tiles[y][x]):
            if hand_actions[i] != ["HARVEST"]:
                hand_actions[i] = ["HARVEST"]
                changed.append({"kind": "early_harvest", "unit": f"hand_{i}", "x": x, "y": y})
    revised["hands"] = hand_actions

    if changed:
        _switch_events.append({
            "day": day,
            "remaining_horizon": remaining,
            "changes": changed,
        })

    return revised


def get_activations():
    return closure.get_activations()


def get_switch_events():
    return copy.deepcopy(_switch_events)


def get_trace():
    return closure.get_trace()
