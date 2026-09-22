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


def option_preservation_meaning(obs, start_day):
    """Pure abstraction probe.

    This intentionally carries no numeric scale, threshold, action, or strategy.
    It only names the strategic frame to make available to the model context.
    """
    day=int(obs.get("day",0) or 0)
    if day < int(start_day):
        return None
    remaining=max(0,30-day)
    return {
        "phase":"OPTION_PRESERVATION",
        "priority":"KEEP_FUTURE_CHOICES_OPEN",
        "risk":"OVER_COMMITMENT",
        "principle":"Do not fix too much of the future at once when optionality is becoming scarce.",
        "source":"flow_abstraction_probe",
        "day":day,
        "remaining":remaining,
        "action_instruction":None,
        "strategy_instruction":None,
        "numeric_rule":None,
    }


def realizable_capacity_meaning(obs, start_day):
    """Abstract search direction only. No domain, action, threshold, or winner."""
    day=int(obs.get("day",0) or 0)
    if day < int(start_day):
        return None
    return {
        "phase":"REALIZABLE_CAPACITY",
        "principle":"Commitment should track realizable capacity, not merely desired capacity. Consider what can realistically be converted into value within the remaining time, resources, and execution capacity.",
        "search_task":"Inspect the current State and discover commitment structures where desired capacity may exceed realizable capacity. Do not assume a predefined domain.",
        "source":"flow_abstraction_reentry",
        "day":day,
        "remaining":max(0,30-day),
        "action_instruction":None,
        "strategy_instruction":None,
        "numeric_rule":None,
        "evidence_status":"hypothesis",
    }
