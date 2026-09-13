"""G17: exclusive pre-registered attribution over unchanged G16 Observe.

Act remains G15 and Observe remains G16. Attribution never changes actions.
At each Probe, an attribution ticket and its rule are frozen. A later sale-like
return can close at most one eligible ticket (oldest first). Unmatched returns
remain Unattributed. This is operational attribution, not causal proof.
"""

import g16_agent as observe

_probe_enabled = True
_attribution_enabled = True
_state = {}


def set_probe_enabled(enabled):
    global _probe_enabled
    _probe_enabled = bool(enabled)
    observe.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    global _attribution_enabled
    _attribution_enabled = bool(enabled)


def _econ(obs):
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    shed = private.get("shed", {})
    inventories = private.get("inventories", [])

    def total(item):
        return shed.get(item, 0) + sum(inv.get(item, 0) for inv in inventories)

    cows = total("COW")
    for row in me.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                cows += 1
    return {
        "day": obs["day"],
        "money": me.get("money", 0),
        "units": 1 + len(me.get("hands", [])),
        "cows": cows,
        "wheat": total("WHEAT"),
        "outputs": sum(total(k) for k in ("MILK", "WOOL", "EGG", "FERTILIZER")),
    }


def reset_telemetry():
    global _state
    observe.set_probe_enabled(_probe_enabled)
    observe.reset_telemetry()
    _state = {"turn": 0, "last_econ": None, "tickets": [], "unattributed_returns": [], "claims": []}


def _update_tickets(now):
    for ticket in _state["tickets"]:
        if ticket["status"] != "open":
            continue
        ticket["age"] += 1
        start = ticket["start"]
        asset_added = now["cows"] > start["cows"] or now["wheat"] > start["wheat"]
        cash_drawdown = now["money"] < start["money"]
        if asset_added and cash_drawdown:
            ticket["investment_seen"] = True
            if ticket["investment_turn"] is None: ticket["investment_turn"] = _state["turn"]
        if ticket["investment_seen"] and now["outputs"] > start["outputs"]:
            ticket["production_seen"] = True
            if ticket["production_turn"] is None: ticket["production_turn"] = _state["turn"]
        if ticket["age"] >= ticket["rule"]["horizon_calls"]:
            ticket["status"] = "expired_unattributed"
            ticket["expired_turn"] = _state["turn"]


def _attribute_return(now, prev):
    if prev is None: return
    released = prev["outputs"] - now["outputs"]
    cash_delta = now["money"] - prev["money"]
    if released <= 0 or cash_delta <= 0: return
    return_event = {"turn": _state["turn"], "day": now["day"], "released_outputs": released, "cash_delta": cash_delta}
    eligible = [
        t for t in _state["tickets"]
        if t["status"] == "open" and t["investment_seen"] and t["production_seen"] and t["start_turn"] < _state["turn"]
    ]
    eligible.sort(key=lambda t: (t["start_turn"], t["probe_id"]))
    if not _attribution_enabled or not eligible:
        event = dict(return_event)
        event["reason"] = "attribution_off" if not _attribution_enabled else "no_eligible_pre_registered_probe"
        _state["unattributed_returns"].append(event)
        return
    ticket = eligible[0]
    ticket["status"] = "attributed_closed"
    ticket["claim_turn"] = _state["turn"]
    ticket["claim_day"] = now["day"]
    ticket["return_event"] = dict(return_event)
    ticket["recovery_calls"] = _state["turn"] - ticket["start_turn"]
    _state["claims"].append({"probe_id": ticket["probe_id"], "return_turn": _state["turn"], "cash_delta": cash_delta, "released_outputs": released})


def agent(obs):
    global _state
    if not _state: reset_telemetry()
    now = _econ(obs)
    prev = _state["last_econ"]
    _update_tickets(now)
    _attribute_return(now, prev)
    before = observe.get_telemetry().get("x_probes", 0)
    action = observe.agent(obs)
    after = observe.get_telemetry().get("x_probes", 0)
    if after > before:
        _state["tickets"].append({
            "probe_id": after, "start_turn": _state["turn"], "start": dict(now),
            "rule": {"registered_at_probe": True, "horizon_calls": 120,
                     "eligibility": "asset_or_input_added_with_cash_drawdown;then_output_observed;then_output_release_with_positive_cash_delta",
                     "allocation": "oldest_eligible_probe_first", "max_claims": 1},
            "age": 0, "investment_seen": False, "investment_turn": None,
            "production_seen": False, "production_turn": None, "status": "open",
            "claim_turn": None, "claim_day": None, "return_event": None, "recovery_calls": None,
        })
    _state["last_econ"] = now
    _state["turn"] += 1
    return action


def get_telemetry():
    base = dict(observe.get_telemetry())
    tickets = _state.get("tickets", [])
    base.update({
        "a_tickets": len(tickets),
        "a_claimed": sum(t["status"] == "attributed_closed" for t in tickets),
        "a_expired": sum(t["status"] == "expired_unattributed" for t in tickets),
        "a_open": sum(t["status"] == "open" for t in tickets),
        "a_unattributed_returns": len(_state.get("unattributed_returns", [])),
        "a_duplicate_claims": max(0, len(_state.get("claims", [])) - len({c["probe_id"] for c in _state.get("claims", [])})),
    })
    return base


def get_trace():
    return {
        "observe": observe.get_trace(),
        "attribution": {
            "enabled": _attribution_enabled,
            "tickets": [dict(t) for t in _state.get("tickets", [])],
            "claims": [dict(c) for c in _state.get("claims", [])],
            "unattributed_returns": [dict(e) for e in _state.get("unattributed_returns", [])],
        },
    }
