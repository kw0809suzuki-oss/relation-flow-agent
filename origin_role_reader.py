"""Neutral Origin-side reader for Role re-entry context.

Constitution:
- Role never emits an action or strategy.
- Role is only observed current-position context.
- Origin-side reading may describe familiarity / ambiguity / support.
- Flow direction remains outside this module.
"""

def read(role_context, origin_internal):
    ctx = dict(role_context or {})
    supports = list(ctx.get("maximal_support", []) or [])
    maximal_count = int(ctx.get("maximal_count", 0) or 0)
    family_count = len(set(ctx.get("maximal_family_ids", []) or []))

    if not supports:
        familiarity = 0.0
        support_min = 0.0
        support_max = 0.0
    else:
        support_min = min(supports)
        support_max = max(supports)
        familiarity = sum(supports) / len(supports)

    ambiguity = 0.0 if maximal_count <= 1 else min(1.0, (maximal_count - 1) / 3.0)
    field_description = dict(ctx.get("field_description", {}) or {})
    field_context_present = bool(ctx.get("field_description_connected", False) and field_description)

    return {
        "role_present": maximal_count > 0,
        "familiarity": round(familiarity, 6),
        "ambiguity": round(ambiguity, 6),
        "support_min": round(support_min, 6),
        "support_max": round(support_max, 6),
        "maximal_role_count": maximal_count,
        "family_count": family_count,
        "origin_strategy_observed": origin_internal.get("strategy_name"),
        "field_context_present": field_context_present,
        "field_description": field_description,
        "flow_direction": None,
        "action_instruction": None,
        "strategy_instruction": field_description.get("strategy_instruction"),
    }
