"""Outer Meaning v0 — public-state abstraction only.

Produces semantic context. It never emits, suppresses, or rewrites actions.
"""
def closure_meaning(obs, start_day):
    day=int(obs.get("day",0) or 0)
    if day < int(start_day):
        return None
    remaining=max(0,30-day)
    return {
        "phase":"CLOSURE",
        "priority":"RECOVER_VALUE",
        "risk":"LONG_PAYBACK",
        "source":"public_state",
        "day":day,
        "remaining":remaining,
        "action_instruction":None,
        "strategy_instruction":None,
    }
