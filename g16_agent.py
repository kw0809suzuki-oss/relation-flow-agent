"""G16: observational closure layer over the unchanged G15 body.

W remains the Act gate inside G15. This module does not alter actions. It watches
whether a probe is followed by an observable economic loop.
"""

import g15_agent as body

_probe_enabled = True
_closure = {}


def set_probe_enabled(enabled):
    global _probe_enabled
    _probe_enabled = bool(enabled)
    body.set_probe_enabled(enabled)


def _econ(obs):
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])

    def total(item):
        return shed.get(item, 0) + sum(inv.get(item, 0) for inv in inventories)

    cows = total("COW")
    farm_cows = 0
    for row in me.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                farm_cows += 1
    outputs = sum(total(k) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
    return {
        "day": obs["day"],
        "money": me.get("money", 0),
        "units": 1 + len(me.get("hands", [])),
        "cows": cows + farm_cows,
        "wheat": total("WHEAT"),
        "outputs": outputs,
    }


def reset_telemetry():
    global _closure
    body.set_probe_enabled(_probe_enabled)
    body.reset_telemetry()
    _closure = {"turn": 0, "last_probe_count": 0, "last_econ": None, "episodes": []}


def _state(ep):
    if ep["closed"]: return "closed"
    if ep["sale_return_seen"] or ep["cash_recovered"]: return "closure_candidate"
    if ep["production_seen"] or ep["investment_seen"]: return "open_loop"
    return "unresolved"


def _observe_episode(ep, now, prev):
    ep["age"] += 1
    ep["min_money"] = min(ep["min_money"], now["money"])
    ep["max_money"] = max(ep["max_money"], now["money"])
    ep["max_cows"] = max(ep["max_cows"], now["cows"])
    ep["max_wheat"] = max(ep["max_wheat"], now["wheat"])
    ep["max_outputs"] = max(ep["max_outputs"], now["outputs"])
    asset_added = now["cows"] > ep["start"]["cows"] or now["wheat"] > ep["start"]["wheat"]
    cash_drawdown = ep["min_money"] < ep["start"]["money"]
    if asset_added and cash_drawdown: ep["investment_seen"] = True
    if now["outputs"] > ep["start"]["outputs"]: ep["production_seen"] = True
    if prev is not None and ep["production_seen"]:
        output_released = now["outputs"] < prev["outputs"]
        cash_returned = now["money"] > prev["money"]
        if output_released and cash_returned: ep["sale_return_seen"] = True
    if ep["investment_seen"] and now["money"] >= ep["start"]["money"]: ep["cash_recovered"] = True
    ep["closed"] = bool(ep["investment_seen"] and ep["production_seen"] and (ep["sale_return_seen"] or ep["cash_recovered"]))
    ep["state"] = _state(ep)
    if ep["closed"] and ep["closed_turn"] is None:
        ep["closed_turn"] = _closure["turn"]
        ep["closed_day"] = now["day"]
        ep["recovery_calls"] = ep["age"]
    if ep["age"] >= 120 and not ep["closed"]:
        ep["finished"] = True
        ep["state"] = "unclosed_at_horizon"


def agent(obs):
    global _closure
    if not _closure: reset_telemetry()
    now = _econ(obs)
    prev = _closure["last_econ"]
    for ep in _closure["episodes"]:
        if not ep["finished"]: _observe_episode(ep, now, prev)
    before = body.get_telemetry().get("x_probes", 0)
    action = body.agent(obs)
    after = body.get_telemetry().get("x_probes", 0)
    if after > before:
        _closure["episodes"].append({
            "probe_index": after, "start_turn": _closure["turn"], "start": dict(now),
            "age": 0, "min_money": now["money"], "max_money": now["money"],
            "max_cows": now["cows"], "max_wheat": now["wheat"], "max_outputs": now["outputs"],
            "investment_seen": False, "production_seen": False, "sale_return_seen": False,
            "cash_recovered": False, "closed": False, "closed_turn": None,
            "closed_day": None, "recovery_calls": None, "finished": False, "state": "unresolved",
        })
    _closure["last_econ"] = now
    _closure["turn"] += 1
    return action


def get_telemetry():
    base = dict(body.get_telemetry())
    episodes = _closure.get("episodes", [])
    base.update({
        "c_episodes": len(episodes),
        "c_closed": sum(ep["closed"] for ep in episodes),
        "c_open_loop": sum(ep["state"] == "open_loop" for ep in episodes),
        "c_candidates": sum(ep["state"] == "closure_candidate" for ep in episodes),
        "c_unclosed": sum(ep["state"] == "unclosed_at_horizon" for ep in episodes),
    })
    return base


def get_trace():
    return {"body": body.get_trace(), "closure": [dict(ep) for ep in _closure.get("episodes", [])]}
