"""Production Agent v3: Expansion-to-Production Bridge.

v2 is frozen. v3 adds one bounded function unit only:
- detect tiles newly unlocked by the existing v2 land expansion
- reserve up to two trailing hands while that short bridge is active
- MOVE to newly unlocked empty tiles
- PLANT using seed choices already present in the existing production plan
- apply the first WATER
- release the hand back to the normal scheduler

No Bundle / Relation / Flow signal is read for runtime control.
"""

import copy

import production_agent_v2_capacity_bridge as base

BRIDGE_WORKERS = 2
BRIDGE_TARGET_LIMIT = 2

_STATS = {
    "turns": 0,
    "unlock_events": 0,
    "targets_added": 0,
    "bridge_worker_actions": 0,
    "bridge_moves": 0,
    "bridge_plants": 0,
    "bridge_waters": 0,
    "targets_completed": 0,
}
_PREV_UNLOCKED = None
_BRIDGE_TARGETS = []


def reset_telemetry():
    global _PREV_UNLOCKED, _BRIDGE_TARGETS
    base.reset_telemetry()
    for k in _STATS:
        _STATS[k] = 0
    _PREV_UNLOCKED = None
    _BRIDGE_TARGETS = []


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v3_expansion_bridge"] = {
        **_STATS,
        "bridge_workers": BRIDGE_WORKERS,
        "bridge_target_limit": BRIDGE_TARGET_LIMIT,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def _move_toward(src, dst):
    x, y = src
    tx, ty = dst
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _unlocked_coords(tiles):
    out = set()
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile != "LOCKED":
                out.add((x, y))
    return out


def _tile_at(tiles, pos):
    x, y = pos
    return tiles[y][x]


def _planned_crop_order(action, private):
    order = []
    for o in action.get("market", []) or []:
        if o and len(o) >= 3 and o[0] == "BUY_SEED" and o[1] not in order:
            order.append(o[1])
    seeds = private.get("seeds", {}) or {}
    for crop in ("WHEAT", "MELON", "STRAWBERRY"):
        if seeds.get(crop, 0) > 0 and crop not in order:
            order.append(crop)
    return order


def _choose_crop(action, private, reserved_seed_use):
    seeds = private.get("seeds", {}) or {}
    for crop in _planned_crop_order(action, private):
        available = int(seeds.get(crop, 0)) - int(reserved_seed_use.get(crop, 0))
        if available > 0:
            return crop
    return None


def _refresh_targets(tiles):
    global _BRIDGE_TARGETS
    keep = []
    for pos in _BRIDGE_TARGETS:
        tile = _tile_at(tiles, pos)
        if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("watered_today", False):
            _STATS["targets_completed"] += 1
            continue
        if tile == "LOCKED":
            continue
        keep.append(pos)
    _BRIDGE_TARGETS = keep


def agent(obs):
    global _PREV_UNLOCKED, _BRIDGE_TARGETS

    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    player = int(obs["player"])
    me = obs["farms"][player]
    tiles = me["tiles"]
    private = obs.get("private", {}) or {}
    unlocked = _unlocked_coords(tiles)

    if _PREV_UNLOCKED is not None:
        newly = sorted(unlocked - _PREV_UNLOCKED)
        if newly:
            empty_new = [p for p in newly if _tile_at(tiles, p) is None]
            if empty_new:
                _STATS["unlock_events"] += 1
                room = max(0, BRIDGE_TARGET_LIMIT - len(_BRIDGE_TARGETS))
                for pos in empty_new[:room]:
                    if pos not in _BRIDGE_TARGETS:
                        _BRIDGE_TARGETS.append(pos)
                        _STATS["targets_added"] += 1
    _PREV_UNLOCKED = unlocked

    _refresh_targets(tiles)
    hands = list(me.get("hands", []) or [])
    if not _BRIDGE_TARGETS or not hands:
        return action

    hand_actions = list(action.get("hands", []) or [])
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])

    # Use trailing hands so the existing G8 livestock lane (farmer + early hands)
    # remains as intact as possible.
    worker_indices = list(range(max(0, len(hands) - BRIDGE_WORKERS), len(hands)))
    available_targets = list(_BRIDGE_TARGETS)
    reserved_seed_use = {}

    for idx in worker_indices:
        if not available_targets:
            break
        pos = tuple(hands[idx])
        target = min(
            available_targets,
            key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]),
        )
        available_targets.remove(target)
        tile = _tile_at(tiles, target)

        override = None
        if pos == target:
            if tile is None:
                crop = _choose_crop(action, private, reserved_seed_use)
                if crop is not None:
                    override = ["PLANT", crop]
                    reserved_seed_use[crop] = reserved_seed_use.get(crop, 0) + 1
                    _STATS["bridge_plants"] += 1
            elif isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today", False):
                override = ["WATER"]
                _STATS["bridge_waters"] += 1
        else:
            # Move only when the target still represents the short bridge task.
            if tile is None or (isinstance(tile, dict) and tile.get("kind") == "PLANT" and not tile.get("watered_today", False)):
                override = _move_toward(pos, target)
                _STATS["bridge_moves"] += 1

        if override is not None:
            hand_actions[idx] = override
            _STATS["bridge_worker_actions"] += 1

    action["hands"] = hand_actions
    return action
