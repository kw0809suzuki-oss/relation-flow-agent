"""Strong Origin v2 Body-only v0.

Default combat body only:
- frozen Strong Origin normal cycle
- original static livestock loop
- adopted D14 expansion closure
- native HIRE preserved

Deliberately excluded:
- G15 resonance / probe controller
- dynamic COW target modulation
- opponent-cycle steering
- Bundle Flow v0
- role/re-entry modulation
- Catalog lookup
- Boundary-driven local repairs

This is not a final v2. It is the first body-only Battle candidate.
"""
import copy

import strong_origin_body as body

STATIC_COW_TARGETS = ((6, 2), (10, 4), (16, 6))
STATIC_FEED_CARRY = 3
D14_START_DAY = 14

_state = {}


def reset_telemetry():
    global _state
    body.COW_TARGETS = STATIC_COW_TARGETS
    body.FEED_CARRY = STATIC_FEED_CARRY
    body.set_reentry_context({})
    body.reset_telemetry()
    _state = {
        "turns": 0,
        "d14_changed_turns": 0,
        "d14_removed_orders": 0,
    }


def _is_d14_expansion(order):
    if not isinstance(order, (list, tuple)) or not order:
        return False
    op = order[0]
    if op in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(order) > 1 and order[1] == "COW"


def _apply_d14(obs, action):
    if not isinstance(action, dict):
        return action, []
    if int(obs.get("day", 0) or 0) < D14_START_DAY:
        return action, []
    market = list(action.get("market", []) or [])
    removed = [copy.deepcopy(x) for x in market if _is_d14_expansion(x)]
    if not removed:
        return action, []
    revised = copy.deepcopy(action)
    revised["market"] = [x for x in market if not _is_d14_expansion(x)]
    return revised, removed


def agent(obs):
    global _state
    if not _state:
        reset_telemetry()

    # Reassert body defaults so a previous baseline run in the same Python
    # process cannot leak G15's dynamic livestock target into this candidate.
    body.COW_TARGETS = STATIC_COW_TARGETS
    body.FEED_CARRY = STATIC_FEED_CARRY
    body.set_reentry_context({})

    action = body.agent(obs)
    action, removed = _apply_d14(obs, action)

    _state["turns"] += 1
    if removed:
        _state["d14_changed_turns"] += 1
        _state["d14_removed_orders"] += len(removed)
    return action


def get_telemetry():
    out = dict(body.get_telemetry())
    out.update({
        "strong_origin_v2_body_only": True,
        "static_cow_targets": [list(x) for x in STATIC_COW_TARGETS],
        "static_feed_carry": STATIC_FEED_CARRY,
        "d14_start_day": D14_START_DAY,
        **_state,
    })
    return out
