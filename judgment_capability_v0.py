"""Judgment Capability v0: State -> observation packet -> open Direction Space.

No action selection.
No battle policy mutation.
No single winning direction.
The output is a structured packet for a later reasoning/generation model.
"""
from copy import deepcopy

from judgment_guide_v0 import JUDGMENT_GUIDE_V0

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
    private = obs.get("private", {}) or {}
    tiles = me.get("tiles", []) or []

    unlocked_tiles = 0
    empty_tiles = 0
    planted = 0
    harvestable = 0
    unwatered = 0
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
                planted += 1
                if float(tile.get("yield_units", 0) or 0) > 0:
                    harvestable += 1
                if not tile.get("watered_today", False):
                    unwatered += 1

    cows = _total(private, "COW") + placed_cows
    wheat = _total(private, "WHEAT")
    product_stock = sum(_total(private, item) for item in PRODUCTS)
    seed_stock = {crop: float((private.get("seeds", {}) or {}).get(crop, 0) or 0) for crop in CROPS}
    units = 1 + len(me.get("hands", []) or [])
    work_backlog = harvestable + unwatered + weeds

    day = int(obs.get("day", 0) or 0)
    remaining = TERMINAL_DAY - day

    return {
        "day": day,
        "remaining_horizon": remaining,
        "money": float(me.get("money", 0) or 0),
        "land_quadrants": len(me.get("unlocked_quadrants", []) or []),
        "unlocked_tiles": unlocked_tiles,
        "empty_tiles": empty_tiles,
        "planted_tiles": planted,
        "hands": len(me.get("hands", []) or []),
        "units": units,
        "cows": cows,
        "wheat_stock": wheat,
        "product_stock": product_stock,
        "seed_stock": seed_stock,
        "harvestable_tiles": harvestable,
        "unwatered_tiles": unwatered,
        "weeds": weeds,
        "work_backlog": work_backlog,
        # Descriptive probe signal only; not a policy rule.
        "feed_pressure_proxy": max(0.0, 2.0 * cows - wheat),
    }


def _add(bucket, condition, message):
    if condition:
        bucket.append(message)


def build_direction_space(state):
    grow_support, grow_counter = [], []
    earn_support, earn_counter = [], []
    recover_support, recover_counter = [], []

    # These are descriptive guide signals, not selection thresholds.
    _add(grow_support, state["remaining_horizon"] > 14, "terminalまで比較的長い時間が残っている")
    _add(grow_support, state["empty_tiles"] > 0, "既存の土地に未使用capacityがある")
    _add(grow_counter, state["remaining_horizon"] <= 14, "残存horizonが短く、追加Expansionの回収余地を慎重に見る必要がある")

    _add(earn_support, state["remaining_horizon"] <= 14, "終盤であり、既存能力からの回収を重く見る材料がある")
    _add(earn_support, state["product_stock"] > 0, "すでにMoneyへ変換可能なproduct stockがある")
    _add(earn_support, state["harvestable_tiles"] > 0, "すでに収穫可能な生産物がある")
    _add(earn_counter, state["remaining_horizon"] > 14 and state["planted_tiles"] == 0, "まだ生産基盤自体が薄い可能性がある")

    _add(recover_support, state["feed_pressure_proxy"] > 0, "cowに対するfeed/input不足proxyが立っている")
    _add(recover_support, state["work_backlog"] > state["units"] * 2, "作業量が現在のunit数に対して大きい")
    _add(recover_counter, state["feed_pressure_proxy"] == 0 and state["work_backlog"] <= state["units"] * 2, "明確なfeed/work詰まりproxyは見えていない")

    return {
        "grow": {
            "meaning": JUDGMENT_GUIDE_V0["directions"]["grow"],
            "support": grow_support,
            "counter": grow_counter,
            "status": "open",
        },
        "earn": {
            "meaning": JUDGMENT_GUIDE_V0["directions"]["earn"],
            "support": earn_support,
            "counter": earn_counter,
            "status": "open",
        },
        "recover": {
            "meaning": JUDGMENT_GUIDE_V0["directions"]["recover"],
            "support": recover_support,
            "counter": recover_counter,
            "status": "open",
        },
    }


def judgment_packet(obs):
    state = observe_state(obs)
    return {
        "schema": "kaggriculture.judgment-capability.v0",
        "state": state,
        "direction_space": build_direction_space(state),
        "boundary": {
            "selection_made": False,
            "action_generated": False,
            "note": "v0 preserves multiple directions and observation evidence only.",
        },
    }


def guide():
    return deepcopy(JUDGMENT_GUIDE_V0)
