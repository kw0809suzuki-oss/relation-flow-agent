"""Seed Horizon Isolation Probe v0.

Battle-side diagnostic wrapper around the frozen Strong Origin body.

Purpose:
Measure whether Remaining Horizon has value as information for the existing
D14 BUY_SEED suppression. This is NOT a new seed-selection policy.

Modes:
A = Current D14. Suppress BUY_LAND / BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW.
B = Seed reopen. Preserve structural closure, but do not suppress BUY_SEED.
C = Harvest-feasible Seed reopen. Preserve structural closure and allow a
    native BUY_SEED request only when, under public crop timing rules and the
    earliest possible plant after this market purchase, the crop can become
    HARVEST-eligible during the playable season.

Important public-engine ordering:
Unit actions execute before market orders. A seed bought this turn cannot be
planted until a later turn.

Important boundary:
C proves only public-rule earliest HARVEST eligibility. It does NOT assert
actual PLANT, actual HARVEST, SELL, Cash return, profitability, or terminal
benefit.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import strong_origin_body as body


STATIC_COW_TARGETS = ((6, 2), (10, 4), (16, 6))
STATIC_FEED_CARRY = 3
D14_START_DAY = 14

# Official 30-day Battle: recorded playable days are 0..29.
LAST_PLAYABLE_DAY = 29
LAST_HOUR = 23

MODE_CURRENT_D14 = "A"
MODE_SEED_REOPEN = "B"
MODE_HARVEST_FEASIBLE_SEED = "C"
VALID_MODES = {
    MODE_CURRENT_D14,
    MODE_SEED_REOPEN,
    MODE_HARVEST_FEASIBLE_SEED,
}

_mode = MODE_CURRENT_D14
_state: Dict[str, Any] = {}


def set_mode(mode: str) -> None:
    global _mode
    mode = str(mode).upper()
    if mode not in VALID_MODES:
        raise ValueError(f"unknown seed horizon mode: {mode}")
    _mode = mode


def get_mode() -> str:
    return _mode


def reset_telemetry() -> None:
    global _state
    body.COW_TARGETS = STATIC_COW_TARGETS
    body.FEED_CARRY = STATIC_FEED_CARRY
    body.set_reentry_context({})
    body.reset_telemetry()
    _state = {
        "turns": 0,
        "changed_turns": 0,
        "removed_orders": 0,
        "native_seed_requests_after_d14": 0,
        "seed_requests_allowed_after_d14": 0,
        "seed_requests_suppressed_after_d14": 0,
        "seed_decisions": [],
    }


def _day_hour(obs: Dict[str, Any]) -> Tuple[int, int]:
    return int(obs.get("day", 0) or 0), int(obs.get("hour", 0) or 0)


def _earliest_plant_day_after_market_purchase(day: int, hour: int) -> int:
    """Earliest day a seed bought in this turn could be planted.

    Unit actions execute before market. Therefore the purchase is unavailable
    to PLANT in the current turn.

    If another turn remains in the same day, earliest plant day is unchanged.
    A purchase at hour 23 can first be planted on the next day.

    This is an optimistic feasibility boundary only; it does not assert that a
    suitable actor/tile/action will actually exist.
    """
    return day + (1 if hour >= LAST_HOUR else 0)


def harvest_feasibility(obs: Dict[str, Any], crop: str) -> Dict[str, Any]:
    day, hour = _day_hour(obs)
    rule = kg.CROPS.get(crop)
    if rule is None:
        return {
            "crop": crop,
            "known_crop": False,
            "allowed": False,
            "day": day,
            "hour": hour,
            "reason": "unknown_crop",
        }

    first_yield_day = int(rule["first_yield_day"])
    earliest_plant_day = _earliest_plant_day_after_market_purchase(day, hour)
    earliest_harvest_day = earliest_plant_day + first_yield_day
    allowed = earliest_harvest_day <= LAST_PLAYABLE_DAY

    return {
        "crop": crop,
        "known_crop": True,
        "day": day,
        "hour": hour,
        "first_yield_day": first_yield_day,
        "earliest_plant_day": earliest_plant_day,
        "earliest_harvest_day": earliest_harvest_day,
        "last_playable_day": LAST_PLAYABLE_DAY,
        "allowed": allowed,
        "reason": (
            "earliest_harvest_within_playable_season"
            if allowed
            else "earliest_harvest_after_playable_season"
        ),
        "boundary": (
            "optimistic public-rule feasibility only; no claim of actual plant, "
            "harvest, sell, cash return, or profit"
        ),
    }


def _is_structural_d14_order(order: Any) -> bool:
    if not isinstance(order, (list, tuple)) or not order:
        return False
    op = order[0]
    if op in ("BUY_LAND", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(order) > 1 and order[1] == "COW"


def _is_seed_order(order: Any) -> bool:
    return (
        isinstance(order, (list, tuple))
        and len(order) > 1
        and order[0] == "BUY_SEED"
    )


def _seed_decision(obs: Dict[str, Any], order: Any, mode: str) -> Dict[str, Any]:
    crop = str(order[1]) if len(order) > 1 else None
    base = {
        "mode": mode,
        "day": int(obs.get("day", 0) or 0),
        "hour": int(obs.get("hour", 0) or 0),
        "order": copy.deepcopy(list(order)),
        "crop": crop,
    }

    if mode == MODE_CURRENT_D14:
        return {
            **base,
            "allowed": False,
            "reason": "current_d14_seed_suppression",
        }

    if mode == MODE_SEED_REOPEN:
        return {
            **base,
            "allowed": True,
            "reason": "seed_reopen_unconditioned",
        }

    return {**base, **harvest_feasibility(obs, crop)}


def filter_action(
    obs: Dict[str, Any],
    action: Any,
    mode: str | None = None,
) -> Tuple[Any, List[Any], List[Dict[str, Any]]]:
    """Apply only the A/B/C D14 filter difference.

    Returns:
      revised_action, removed_orders, seed_decisions
    """
    mode = (mode or _mode).upper()
    if mode not in VALID_MODES:
        raise ValueError(f"unknown seed horizon mode: {mode}")
    if not isinstance(action, dict):
        return action, [], []

    day = int(obs.get("day", 0) or 0)
    if day < D14_START_DAY:
        return action, [], []

    market = list(action.get("market", []) or [])
    kept = []
    removed = []
    decisions: List[Dict[str, Any]] = []

    for order in market:
        if _is_structural_d14_order(order):
            removed.append(copy.deepcopy(order))
            continue

        if _is_seed_order(order):
            decision = _seed_decision(obs, order, mode)
            decisions.append(decision)
            if decision["allowed"]:
                kept.append(order)
            else:
                removed.append(copy.deepcopy(order))
            continue

        kept.append(order)

    if len(kept) == len(market):
        return action, [], decisions

    revised = copy.deepcopy(action)
    revised["market"] = kept
    return revised, removed, decisions


def agent(obs: Dict[str, Any]):
    global _state
    if not _state:
        reset_telemetry()

    # Reassert frozen body defaults so sequential experimental arms cannot leak
    # body-global state into one another.
    body.COW_TARGETS = STATIC_COW_TARGETS
    body.FEED_CARRY = STATIC_FEED_CARRY
    body.set_reentry_context({})

    native_action = body.agent(obs)
    revised, removed, decisions = filter_action(obs, native_action, _mode)

    _state["turns"] += 1
    if removed:
        _state["changed_turns"] += 1
        _state["removed_orders"] += len(removed)

    for d in decisions:
        _state["native_seed_requests_after_d14"] += 1
        if d["allowed"]:
            _state["seed_requests_allowed_after_d14"] += 1
        else:
            _state["seed_requests_suppressed_after_d14"] += 1
        _state["seed_decisions"].append(copy.deepcopy(d))

    return revised


def get_telemetry() -> Dict[str, Any]:
    out = dict(body.get_telemetry())
    out.update(
        {
            "seed_horizon_isolation_probe": True,
            "mode": _mode,
            "d14_start_day": D14_START_DAY,
            "last_playable_day": LAST_PLAYABLE_DAY,
            "static_cow_targets": [list(x) for x in STATIC_COW_TARGETS],
            "static_feed_carry": STATIC_FEED_CARRY,
            **_state,
            "boundary": [
                "A/B/C modify only the D14 market filter; Frozen Body action generation is unchanged.",
                "B restores native BUY_SEED requests without adding new seed-selection logic.",
                "C filters native BUY_SEED requests only by optimistic public-rule earliest HARVEST eligibility.",
                "A seed bought this turn cannot be planted in the same turn because unit actions execute before market.",
                "C does not claim actual PLANT, HARVEST, SELL, Cash return, profit, or terminal value.",
            ],
        }
    )
    return out
