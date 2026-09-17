"""One-shot Day9-10 low-price MILK sell hold.

Minimal intervention: if baseline v6 chooses SELL MILK during Day9-10 and the
current MILK price is < 180, remove only that SELL action once per match.
Next turn is handed back to baseline v6 normally; no forced sell/re-hold.
"""
import whole_flow_control_agent as v6

PRICE_THRESHOLD = 180.0
_hold_used = False


def reset_experiment():
    global _hold_used
    _hold_used = False


def _day(obs):
    # Kaggriculture observations used elsewhere expose day directly; keep a
    # conservative fallback for compatible variants.
    if isinstance(obs, dict):
        if "day" in obs:
            return int(obs.get("day") or 0)
        world = obs.get("world", {})
        if isinstance(world, dict) and "day" in world:
            return int(world.get("day") or 0)
    return 0


def _milk_price(obs):
    try:
        return float(obs["market"]["prices"]["MILK"])
    except (KeyError, TypeError, ValueError):
        return None


def _is_sell_milk(action):
    return isinstance(action, (list, tuple)) and len(action) >= 2 and action[0] == "SELL" and action[1] == "MILK"


def agent(obs):
    global _hold_used
    actions = v6.agent(obs)
    if _hold_used:
        return actions

    day = _day(obs)
    price = _milk_price(obs)
    if day not in (9, 10) or price is None or price >= PRICE_THRESHOLD:
        return actions

    if not any(_is_sell_milk(a) for a in actions):
        return actions

    _hold_used = True
    return [a for a in actions if not _is_sell_milk(a)]
