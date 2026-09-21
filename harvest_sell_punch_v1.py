"""One-punch experiment: shorten harvest -> sell without redesigning the Agent.

Hypothesis only: terminal may improve if harvested shed products are liquidated
immediately. Existing policy remains the base; this wrapper changes market output
only when sellable shed stock exists.
"""
import whole_flow_control_agent as base

SELLABLE = ("WHEAT", "STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "FERTILIZER")


def _sell_orders(obs):
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    orders = []
    for item in SELLABLE:
        qty = shed.get(item, 0)
        if isinstance(qty, (int, float)) and qty > 0:
            orders.append(["SELL", item, qty])
    return orders


def agent(obs):
    action = base.agent(obs)
    if not isinstance(action, dict):
        return action
    sells = _sell_orders(obs)
    if not sells:
        return action
    market = action.get("market", []) or []
    non_sells = [x for x in market if not (isinstance(x, list) and x and x[0] == "SELL")]
    out = dict(action)
    out["market"] = (sells + non_sells)[:10]
    return out


def __getattr__(name):
    return getattr(base, name)
