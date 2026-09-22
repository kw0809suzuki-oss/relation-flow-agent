"""Model-side Selection -> Direction representation v0.

Transforms the model's own candidate selection into a state-transition direction.
It does not select an Action.

The representation is intentionally descriptive:
- what selected crop the model is trying to move toward;
- what the current state already provides;
- which observed constraints block that direction;
- which executable surfaces are currently open.

Unknown/missing values remain unknown rather than being invented.
"""

SEED_COST = {"WHEAT": 10, "STRAWBERRY": 100, "MELON": 80}
FIRST_YIELD = {"WHEAT": 2, "STRAWBERRY": 10, "MELON": 10}


def build(candidate_selection, origin_internal):
    selection = dict(candidate_selection or {})
    chosen = selection.get("selected_candidate")
    internal = dict(origin_internal or {})

    if not isinstance(chosen, (list, tuple)) or len(chosen) < 2 or chosen[0] != "BUY_SEED":
        return None

    crop = str(chosen[1])
    if crop not in SEED_COST:
        return None

    targets = dict(internal.get("targets", {}) or {})
    live = dict(internal.get("live_plants", {}) or {})
    seeds = dict(internal.get("seed_stock", {}) or {})

    target = targets.get(crop)
    live_count = live.get(crop)
    seed_stock = seeds.get(crop)
    money = internal.get("money")
    reserve = internal.get("reserve")
    empty_tiles = internal.get("empty_tile_count")
    remaining_days = internal.get("remaining_days")

    known_need = None
    if all(isinstance(v, (int, float)) for v in (target, live_count, seed_stock)):
        known_need = max(0, int(target - live_count - seed_stock))

    affordable = None
    if isinstance(money, (int, float)) and isinstance(reserve, (int, float)):
        affordable = (money - reserve) >= SEED_COST[crop]

    time_viable = None
    if isinstance(remaining_days, (int, float)):
        time_viable = remaining_days > FIRST_YIELD[crop] + 1

    blockers = []
    if known_need == 0:
        blockers.append("native_target_already_covered")
    if affordable is False:
        blockers.append("insufficient_cash_above_reserve")
    if isinstance(empty_tiles, (int, float)) and empty_tiles <= 0:
        blockers.append("no_empty_tile")
    if time_viable is False:
        blockers.append("insufficient_remaining_days")

    executable = []
    if known_need is not None and known_need > 0 and affordable is True and time_viable is not False:
        executable.append("BUY_SEED")
    if (
        isinstance(seed_stock, (int, float))
        and seed_stock > 0
        and isinstance(empty_tiles, (int, float))
        and empty_tiles > 0
        and time_viable is not False
    ):
        executable.append("PLANT")

    return {
        "direction_type": "selected_crop_state_transition",
        "selected_crop": crop,
        "direction_hypothesis": f"move state toward making {crop} production executable",
        "state_reading": {
            "target": target,
            "live_plants": live_count,
            "seed_stock": seed_stock,
            "native_need": known_need,
            "money": money,
            "reserve": reserve,
            "empty_tiles": empty_tiles,
            "remaining_days": remaining_days,
            "seed_cost": SEED_COST[crop],
        },
        "blockers": blockers,
        "executable_surfaces": executable,
        "action_selection": None,
        "target_rewrite": None,
        "scalar_score": None,
        "weights": None,
    }
