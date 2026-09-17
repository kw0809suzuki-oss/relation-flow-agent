"""One-shot Day9-10 low-price MILK sell hold.

Minimal intervention: if baseline v6 chooses SELL MILK during Day9-10 and the
current MILK price is < 180, remove only that SELL action once per match.
Next turn is handed back to baseline v6 normally; no forced sell/re-hold.
"""
import whole_flow_control_agent as v6

PRICE_THRESHOLD = 180.0
_hold_used = False
_hold_count = 0


def reset_experiment():
    global _hold_used, _hold_count
    _hold_used = False
    _hold_count = 0


def get_hold_count():
    return _hold_count


def _day(obs):
    return int(obs.get("day", 0)) if isinstance(obs, dict) else 0


def _milk_price(obs):
    try:
        return float(obs["market"]["prices"]["MILK"])
    except (KeyError, TypeError, ValueError):
        return None


def _is_sell_milk(action):
    return isinstance(action, (list, tuple)) and len(action) >= 2 and action[0] == "SELL" and action[1] == "MILK"


def agent(obs):
    global _hold_used, _hold_count
    actions = v6.agent(obs)
    if _hold_used:
        return actions

    day = _day(obs)
    price = _milk_price(obs)
    if day not in (9, 10) or price is None or price >= PRICE_THRESHOLD:
        return actions

    # v6 returns a dict: {farmer, hands, market}. Only the market list contains SELLs.
    market = actions.get("market", []) if isinstance(actions, dict) else []
    if not any(_is_sell_milk(a) for a in market):
        return actions

    _hold_used = True
    _hold_count += 1
    revised = dict(actions)
    revised["market"] = [a for a in market if not _is_sell_milk(a)]
    return revised
