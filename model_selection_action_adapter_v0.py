"""Model-side Selection-to-Action Adapter v0.

This adapter does not choose a candidate. It only lets the model use the
candidate it already selected on the previous re-entry.

Current scope:
- selected candidate must be an existing BUY_SEED proposal;
- if that exact BUY_SEED order still exists, move it to the front of BUY_SEED orders;
- when the model is already about to PLANT on an empty tile, prefer the crop it
  selected if that seed is currently available.

No candidate is invented, no purchase quantity is changed, and no target,
strategy, score, or Flow-chan lens is rewritten.
"""

import copy


def _selected_crop(integration):
    selection = dict((integration or {}).get("candidate_selection", {}) or {})
    chosen = selection.get("selected_candidate")
    if not isinstance(chosen, (list, tuple)) or len(chosen) < 3:
        return None, None
    if chosen[0] != "BUY_SEED":
        return None, None
    return str(chosen[1]), list(chosen)


def apply(obs, action, integration):
    crop, chosen_order = _selected_crop(integration)
    if crop is None or not isinstance(action, dict):
        return action, {
            "selection_available": False,
            "market_priority_changed": False,
            "plant_priority_changed": False,
        }

    revised = copy.deepcopy(action)
    market_changed = False
    plant_changed = False

    # Use the model's own selected purchase when it is still among its proposals.
    market = list(revised.get("market", []) or [])
    seed_indices = [
        i for i, order in enumerate(market)
        if isinstance(order, (list, tuple)) and order and order[0] == "BUY_SEED"
    ]
    selected_index = None
    for i in seed_indices:
        if list(market[i]) == chosen_order:
            selected_index = i
            break
    if selected_index is not None and seed_indices and selected_index != seed_indices[0]:
        order = market.pop(selected_index)
        market.insert(seed_indices[0], order)
        revised["market"] = market
        market_changed = True

    # If the model is already planting now, let its own selected crop guide
    # which available seed it plants. This does not create a new planting act.
    private = dict((obs or {}).get("private", {}) or {})
    seeds = dict(private.get("seeds", {}) or {})
    available = int(seeds.get(crop, 0) or 0)

    def prefer_selected(unit_action):
        nonlocal available, plant_changed
        if (
            available > 0
            and isinstance(unit_action, (list, tuple))
            and len(unit_action) >= 2
            and unit_action[0] == "PLANT"
            and unit_action[1] != crop
        ):
            available -= 1
            plant_changed = True
            return ["PLANT", crop]
        return unit_action

    revised["farmer"] = prefer_selected(revised.get("farmer"))
    revised["hands"] = [prefer_selected(a) for a in list(revised.get("hands", []) or [])]

    return revised, {
        "selection_available": True,
        "selected_crop": crop,
        "market_priority_changed": market_changed,
        "plant_priority_changed": plant_changed,
    }
