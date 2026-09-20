"""Judgment Capability v1 packet builder.

State -> observable facts + relation hints + evidence + boundaries.
No direction scoring.
No direction selection.
No action generation.
"""
from copy import deepcopy

from judgment_guide_v1 import JUDGMENT_GUIDE_V1

TERMINAL_DAY = 30
PRODUCTS = ("MILK", "WOOL", "EGG", "FERTILIZER")
CROPS = ("WHEAT", "STRAWBERRY", "MELON")


def _stores(private):
    return [private.get("shed", {}) or {}] + list(private.get("inventories", []) or [])


def _total(private, item):
    total = 0.0
    for store in _stores(private):
        if isinstance(store, dict):
            value = store.get(item, 0)
            if isinstance(value, (int, float)):
                total += float(value)
    return total


def observe_state(obs):
    player = int(obs["player"])
    me = obs["farms"][player]
    opp = obs["farms"][1 - player]
    private = obs.get("private", {}) or {}
    tiles = me.get("tiles", []) or []

    unlocked_tiles = 0
    empty_tiles = 0
    planted_tiles = 0
    harvestable_tiles = 0
    unwatered_tiles = 0
    weeds = 0
    placed_cows = 0

    for row in tiles:
        for tile in row or []:
            if tile == "LOCKED":
                continue
            unlocked_tiles += 1
            if tile is None:
                empty_tiles += 1
                continue
            if not isinstance(tile, dict):
                continue
            if tile.get("animal") == "COW":
                placed_cows += 1
            kind = tile.get("kind")
            if kind == "WEED":
                weeds += 1
            elif kind == "PLANT":
                planted_tiles += 1
                if float(tile.get("yield_units", 0) or 0) > 0:
                    harvestable_tiles += 1
                if not tile.get("watered_today", False):
                    unwatered_tiles += 1

    cows = _total(private, "COW") + placed_cows
    wheat = _total(private, "WHEAT")
    product_inventory = {item: _total(private, item) for item in PRODUCTS}
    seed_inventory = {
        crop: float((private.get("seeds", {}) or {}).get(crop, 0) or 0)
        for crop in CROPS
    }

    day = int(obs.get("day", 0) or 0)
    remaining_days = TERMINAL_DAY - day
    hands = len(me.get("hands", []) or [])

    return {
        "time": {
            "day": day,
            "remaining_days": remaining_days,
        },
        "money": {
            "self": float(me.get("money", 0) or 0),
            "opponent": float(opp.get("money", 0) or 0),
        },
        "capacity": {
            "land_quadrants": len(me.get("unlocked_quadrants", []) or []),
            "unlocked_tiles": unlocked_tiles,
            "empty_tiles": empty_tiles,
            "planted_tiles": planted_tiles,
            "hands": hands,
            "cows": cows,
        },
        "flow_inputs": {
            "wheat_stock": wheat,
            "seed_inventory": seed_inventory,
        },
        "flow_outputs": {
            "harvestable_tiles": harvestable_tiles,
            "product_inventory": product_inventory,
        },
        "work_state": {
            "unwatered_tiles": unwatered_tiles,
            "weeds": weeds,
            "visible_backlog_components": {
                "harvestable": harvestable_tiles,
                "unwatered": unwatered_tiles,
                "weeds": weeds,
            },
        },
    }


def build_packet(obs, human_direction=None):
    return {
        "schema": "kaggriculture.judgment-capability.v1",
        "observed_state": observe_state(obs),
        "human_direction": human_direction,
        "relation_hints": deepcopy(JUDGMENT_GUIDE_V1["relation_hints"]),
        "known_evidence": deepcopy(JUDGMENT_GUIDE_V1["known_evidence"]),
        "judgment_boundaries": deepcopy(JUDGMENT_GUIDE_V1["boundaries"]),
        "candidate_direction_names": deepcopy(JUDGMENT_GUIDE_V1["candidate_directions"]),
        "execution_ai_task": {
            "instruction": (
                "Observed StateとRelation Hintsを使い、grow / earn / recoverの必要性を"
                "複数保持してよい形で解釈する。各方向について根拠と未確定点を示す。"
                "具体Actionはまだ選ばない。"
            ),
            "required_output": {
                "directions": {
                    "grow": {"support": [], "counter": [], "uncertain": []},
                    "earn": {"support": [], "counter": [], "uncertain": []},
                    "recover": {"support": [], "counter": [], "uncertain": []},
                },
                "cross_direction_tensions": [],
                "missing_evidence": [],
            },
        },
        "boundary": {
            "direction_precomputed": False,
            "action_precomputed": False,
            "selection_precomputed": False,
        },
    }


def guide():
    return deepcopy(JUDGMENT_GUIDE_V1)
