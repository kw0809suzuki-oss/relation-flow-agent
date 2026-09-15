"""Observation-only Bundle surface for Production Agent v1.

Records production capacity, self queue state, market state and action counts.
The observer never changes actions and never feeds Bundle values back to control.
"""

import copy
from collections import Counter

import production_agent_v1 as body

_state = {}


def reset():
    global _state
    body.reset_telemetry()
    _state = {"turn": 0, "days": {}}


def _public(farm):
    animals = Counter()
    active = planted = 0
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if tile in (None, "LOCKED"):
                continue
            active += 1
            if isinstance(tile, dict):
                if tile.get("animal"):
                    animals[str(tile.get("animal"))] += 1
                if tile.get("crop") or tile.get("plant"):
                    planted += 1
    return {
        "money": farm.get("money", 0),
        "hands": len(farm.get("hands", []) or []),
        "land": len(farm.get("unlocked_quadrants", []) or []),
        "active_tiles": active,
        "planted_tiles": planted,
        "animals": dict(animals),
        "animal_total": sum(animals.values()),
    }


def _private(obs):
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    invs = private.get("inventories", []) or []
    inv = Counter(shed)
    for x in invs:
        inv.update(x or {})
    me = obs["farms"][int(obs["player"])]
    unfed = uncared = ready = cows = 0
    for row in me.get("tiles", []) or []:
        for tile in row:
            if not isinstance(tile, dict) or tile.get("animal") != "COW":
                continue
            cows += 1
            if not tile.get("fed_today", False):
                unfed += 1
            elif not tile.get("cared_today", False):
                uncared += 1
            if tile.get("yield_units", 0) > 0:
                ready += 1
    produce = sum(inv.get(k, 0) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
    return {
        "wheat": inv.get("WHEAT", 0),
        "produce_inventory": produce,
        "cows_on_farm": cows,
        "unfed_cows": unfed,
        "care_wait_cows": uncared,
        "harvest_ready_cows": ready,
    }


def _action_counts(action):
    c = Counter()
    units = [action.get("farmer", ["PASS"]), *(action.get("hands", []) or [])]
    for a in units:
        if not a:
            continue
        k = a[0]
        if k in {"NORTH", "SOUTH", "EAST", "WEST"}:
            c["move"] += 1
        elif k in {"FEED", "CARE", "HARVEST", "DROP", "PICKUP", "DIG", "PLANT", "WATER", "PLACE", "BUILD_PASTURE", "COLLECT_FERTILIZER"}:
            c[k.lower()] += 1
            c["work"] += 1
        elif k == "PASS":
            c["pass"] += 1
    for o in action.get("market", []) or []:
        if not o:
            continue
        if o[0] == "SELL": c["sell_order"] += 1
        elif o[0] == "BUY_PRODUCT" and len(o) > 1 and o[1] == "WHEAT": c["buy_wheat"] += 1
        elif o[0] == "BUY_ANIMAL": c["buy_animal"] += 1
        elif o[0] == "HIRE": c["hire"] += 1
        elif o[0] == "BUY_LAND": c["buy_land"] += 1
    return c


def agent(obs):
    if not _state:
        reset()
    day = int(obs.get("day", 0))
    player = int(obs["player"])
    market = obs.get("market", {}) or {}
    rec = _state["days"].setdefault(day, {
        "day": day,
        "last": None,
        "actions": Counter(),
    })
    rec["last"] = {
        "turn": _state["turn"],
        "self": _public(obs["farms"][player]),
        "opponent": _public(obs["farms"][1-player]),
        "self_private": _private(obs),
        "market": {
            "prices": copy.deepcopy(market.get("prices", {}) or {}),
            "inventory": copy.deepcopy(market.get("inventory", {}) or {}),
        },
    }
    action = body.agent(obs)
    rec["actions"].update(_action_counts(action))
    _state["turn"] += 1
    return action


def get_bundle():
    days = []
    for day in sorted(_state.get("days", {})):
        rec = _state["days"][day]
        days.append({
            "day": day,
            "snapshot": copy.deepcopy(rec["last"]),
            "actions": dict(rec["actions"]),
        })
    return {
        "schema": "production-bundle.v1",
        "constructed_without_terminal": True,
        "control_added": False,
        "days": days,
    }
