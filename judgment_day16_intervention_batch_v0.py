"""Batch concrete interventions for Day16 recover Judgment claim.

Claim remains abstract:
recover may be realized by reducing incoming workload, increasing work capacity,
or reprioritizing existing work.

These are concrete probes only. None is an adopted rule.
"""
import copy

TARGET_DAY = 16

CANDIDATES = {
    "reduce_new_workload": {
        "facet": "reduce_workload",
        "description": "Suppress BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW on Day16.",
    },
    "cap_hire_to_one": {
        "facet": "capacity_balance",
        "description": "Keep at most one HIRE order on Day16.",
    },
    "suppress_hire": {
        "facet": "capacity_balance",
        "description": "Suppress all HIRE orders on Day16.",
    },
    "add_one_hire": {
        "facet": "increase_capacity",
        "description": "Append one HIRE order on Day16.",
    },
    "prioritize_current_harvest": {
        "facet": "reprioritize_work",
        "description": "If farmer is on harvestable output, force HARVEST on Day16.",
    },
}


def _is_workload_purchase(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    op = action[0]
    if op in ("BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(action) > 1 and action[1] == "COW"


def _is_hire(action):
    return isinstance(action, (list, tuple)) and action and action[0] == "HIRE"


def _harvestable_here(obs):
    player = obs["player"]
    me = obs["farms"][player]
    pos = me.get("farmer")
    tiles = me.get("tiles", []) or []
    if not pos or len(pos) != 2:
        return False
    x, y = pos
    if not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
        return False
    tile = tiles[y][x]
    return (
        isinstance(tile, dict)
        and tile.get("kind") == "PLANT"
        and float(tile.get("yield_units", 0) or 0) > 0
    )


def apply_candidate(obs, native_action, candidate_id):
    if candidate_id not in CANDIDATES:
        raise KeyError(candidate_id)

    action = copy.deepcopy(native_action)
    events = []
    if int(obs.get("day", 0) or 0) != TARGET_DAY or not isinstance(action, dict):
        return action, events

    market = list(action.get("market", []) or [])

    if candidate_id == "reduce_new_workload":
        removed = [a for a in market if _is_workload_purchase(a)]
        if removed:
            action["market"] = [a for a in market if not _is_workload_purchase(a)]
            events.append({"kind": candidate_id, "removed": copy.deepcopy(removed)})

    elif candidate_id == "cap_hire_to_one":
        seen = 0
        kept = []
        removed = []
        for order in market:
            if _is_hire(order):
                seen += 1
                if seen > 1:
                    removed.append(order)
                    continue
            kept.append(order)
        if removed:
            action["market"] = kept
            events.append({"kind": candidate_id, "removed_hire_count": len(removed)})

    elif candidate_id == "suppress_hire":
        kept = [a for a in market if not _is_hire(a)]
        if len(kept) != len(market):
            action["market"] = kept
            events.append({"kind": candidate_id, "removed_hire_count": len(market) - len(kept)})

    elif candidate_id == "add_one_hire":
        action["market"] = market + [["HIRE"]]
        events.append({"kind": candidate_id, "added": ["HIRE"]})

    elif candidate_id == "prioritize_current_harvest":
        if _harvestable_here(obs):
            before = copy.deepcopy(action.get("farmer"))
            action["farmer"] = ["HARVEST"]
            events.append({"kind": candidate_id, "before": before, "after": ["HARVEST"]})

    return action, events
