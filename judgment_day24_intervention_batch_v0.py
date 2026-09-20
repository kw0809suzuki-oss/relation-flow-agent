"""Day24 Judgment conflict probes v0.

Conflict:
B = closure-oriented: hold all new expansion on one eligible Day24 call.
C = short-grow-oriented: hold long-horizon assets but leave seed growth available.

These are concrete projections only, not adopted policies.
"""
import copy

TARGET_DAY = 24
SCOPE_CONTRACT = {
    "trigger": "first eligible call on Day24",
    "max_activations": 1,
    "reset": "immediately after activation",
}

CANDIDATES = {
    "B_hold_all_expansion": {
        "description": "Suppress BUY_LAND / BUY_SEED / BUY_ANIMAL / BUY_PRODUCT COW.",
    },
    "C_hold_long_assets_keep_seed": {
        "description": "Suppress BUY_LAND / BUY_ANIMAL / BUY_PRODUCT COW; preserve BUY_SEED.",
    },
}


def new_scope_state():
    return {"activations": 0, "closed": False}


def _is_cow_product(action):
    return (
        isinstance(action, (list, tuple))
        and len(action) > 1
        and action[0] == "BUY_PRODUCT"
        and action[1] == "COW"
    )


def _is_all_expansion(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    return action[0] in ("BUY_LAND", "BUY_SEED", "BUY_ANIMAL") or _is_cow_product(action)


def _is_long_asset(action):
    if not isinstance(action, (list, tuple)) or not action:
        return False
    return action[0] in ("BUY_LAND", "BUY_ANIMAL") or _is_cow_product(action)


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

    if candidate_id == "B_hold_all_expansion":
        removed = [a for a in market if _is_all_expansion(a)]
        if not removed:
            return action, events
        action["market"] = [a for a in market if not _is_all_expansion(a)]

    elif candidate_id == "C_hold_long_assets_keep_seed":
        removed = [a for a in market if _is_long_asset(a)]
        if not removed:
            return action, events
        action["market"] = [a for a in market if not _is_long_asset(a)]

    scope_state["activations"] += 1
    scope_state["closed"] = True
    events.append({
        "kind": candidate_id,
        "removed": copy.deepcopy(removed),
        "scope": copy.deepcopy(SCOPE_CONTRACT),
        "activation_index": scope_state["activations"],
    })
    return action, events
