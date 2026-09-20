"""Day8 Flow/Resource Judgment claim v0.

Claim:
When visible work-flow blockage is high, reducing incoming workload or increasing
work capacity may be meaningful realizations of recover before choosing a
cash/expansion direction.

Expected observable change:
- visible backlog components should improve or grow more slowly
- hands may increase for the capacity realization
- the claim is not judged from terminal score alone

Concrete interventions are probes only.
"""
import copy

TARGET_DAY = 8
SCOPE_CONTRACT = {
    "trigger": "first eligible call on Day8",
    "max_activations": 1,
    "reset": "immediately after activation",
}

CANDIDATES = {
    "F_reduce_new_workload": {
        "description": "Suppress BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW on first eligible Day8 call.",
    },
    "F_increase_work_capacity": {
        "description": "Append one HIRE on first eligible Day8 call.",
    },
}


def new_scope_state():
    return {"activations": 0, "closed": False}


def _is_workload_purchase(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    op = action[0]
    if op in ("BUY_SEED", "BUY_ANIMAL"):
        return True
    return op == "BUY_PRODUCT" and len(action) > 1 and action[1] == "COW"


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

    if candidate_id == "F_reduce_new_workload":
        removed = [a for a in market if _is_workload_purchase(a)]
        if not removed:
            return action, events
        action["market"] = [a for a in market if not _is_workload_purchase(a)]
        events.append({"kind": candidate_id, "removed": copy.deepcopy(removed)})
        changed = True

    elif candidate_id == "F_increase_work_capacity":
        action["market"] = market + [["HIRE"]]
        events.append({"kind": candidate_id, "added": ["HIRE"]})
        changed = True

    if changed:
        scope_state["activations"] += 1
        scope_state["closed"] = True
        for e in events:
            e["scope"] = copy.deepcopy(SCOPE_CONTRACT)
            e["activation_index"] = scope_state["activations"]

    return action, events
