"""Day8 low-price MILK monetization rescue on top of COW suppression.

Intervention:
- preserve COW First Purchase Suppress v0 exactly
- on Day8 only, if the resulting native/cow policy chooses SELL MILK
  while current MILK price is < 180, remove only SELL MILK once
- next turn returns to the COW-suppression policy normally

This is a Battle candidate derived from the observed accident3 separator.
It is not an adopted rule.
"""
import copy

import cow_first_purchase_suppress_v0 as cow

PRICE_THRESHOLD = 180.0
TARGET_DAY = 8

_hold_used = False
_hold_events = []


def reset_experiment():
    global _hold_used, _hold_events
    _hold_used = False
    _hold_events = []
    cow.reset_experiment()


def _milk_price(obs):
    try:
        return float(obs["market"]["prices"]["MILK"])
    except (KeyError, TypeError, ValueError):
        return None


def _is_sell_milk(action):
    return (
        isinstance(action, (list, tuple))
        and len(action) >= 2
        and action[0] == "SELL"
        and action[1] == "MILK"
    )


def agent(obs):
    global _hold_used

    actions = cow.agent(obs)
    if _hold_used or not isinstance(actions, dict):
        return actions

    try:
        day = int(obs.get("day", 0))
    except (TypeError, ValueError):
        day = 0
    price = _milk_price(obs)

    if day != TARGET_DAY or price is None or price >= PRICE_THRESHOLD:
        return actions

    market = list(actions.get("market", []) or [])
    hits = [a for a in market if _is_sell_milk(a)]
    if not hits:
        return actions

    revised = copy.deepcopy(actions)
    revised["market"] = [a for a in market if not _is_sell_milk(a)]

    _hold_used = True
    _hold_events.append({
        "day": day,
        "hour": obs.get("hour"),
        "milk_price": price,
        "before_market": copy.deepcopy(market),
        "after_market": copy.deepcopy(revised["market"]),
        "removed_sell_milk": copy.deepcopy(hits),
    })
    return revised


def get_hold_events():
    return copy.deepcopy(_hold_events)


def get_hold_count():
    return len(_hold_events)


def get_cow_activations():
    return cow.get_activations()
