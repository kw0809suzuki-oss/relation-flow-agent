"""Day16 Judgment intervention batch v0.1.

Same three concrete probes as before, now under one shared single-shot scope:
- trigger: first eligible call on Day16
- max_activations: 1
- reset: immediately after activation

This changes intervention scope only. It does not change the Judgment claim.
"""
import copy

TARGET_DAY = 16
SCOPE_CONTRACT = {
    "trigger": "first eligible call on Day16",
    "max_activations": 1,
    "reset": "immediately after activation",
}

CANDIDATES = {
    "cap_hire_to_one": {
        "facet": "capacity_balance",
        "description": "Keep at most one HIRE order on the first eligible Day16 call.",
    },
    "suppress_hire": {
        "facet": "capacity_balance",
        "description": "Suppress all HIRE orders on the first eligible Day16 call.",
    },
    "add_one_hire": {
        "facet": "increase_capacity",
        "description": "Append one HIRE order on the first eligible Day16 call.",
    },
}


def new_scope_state():
    return {"activations": 0, "closed": False}


def _is_hire(action):
    return isinstance(action, (list, tuple)) and action and action[0] == "HIRE"


def apply_candidate(obs, native_action, candidate_id, scope_state):
    if candidate_id not in CANDIDATES:
        raise KeyError(candidate_id)

    action = copy.deepcopy(native_action)
    events = []

    if scope_state.get("closed"):
        return action, events

    if int(obs.get("day", 0) or 0) != TARGET_DAY or not isinstance(action, dict):
        return action, events

    market = list(action.get("market", []) or [])
    changed = False

    if candidate_id == "cap_hire_to_one":
        hires = [a for a in market if _is_hire(a)]
        if len(hires) <= 1:
            return action, events
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
        action["market"] = kept
        events.append({
            "kind": candidate_id,
            "removed_hire_count": len(removed),
        })
        changed = True

    elif candidate_id == "suppress_hire":
        hires = [a for a in market if _is_hire(a)]
        if not hires:
            return action, events
        action["market"] = [a for a in market if not _is_hire(a)]
        events.append({
            "kind": candidate_id,
            "removed_hire_count": len(hires),
        })
        changed = True

    elif candidate_id == "add_one_hire":
        action["market"] = market + [["HIRE"]]
        events.append({
            "kind": candidate_id,
            "added": ["HIRE"],
        })
        changed = True

    if changed:
        scope_state["activations"] = scope_state.get("activations", 0) + 1
        if scope_state["activations"] >= SCOPE_CONTRACT["max_activations"]:
            scope_state["closed"] = True
        for event in events:
            event["scope"] = copy.deepcopy(SCOPE_CONTRACT)
            event["activation_index"] = scope_state["activations"]

    return action, events
