"""Remaining-Time x Recovery-Time Gate v1.

Minimal matched-A/B intervention on the existing baseline:
when the baseline wants to start a clearly new investment late in the match,
suppress only that market BUY if the remaining horizon is shorter than a
conservative recovery allowance inferred from Cash Flow Time Profile v2.

This is intentionally not a "sell at Day25" rule.  It tests the Relation:
remaining time versus expected recovery time.  SELL and existing liquidation
actions are left untouched.
"""
import whole_flow_control_agent as v6

TOTAL_DAYS = 30
DAY_CALLS = 24
# v2 observed late high-terminal recovery around 1.72 turns; use 2 observed
# turns plus one full-day slack before allowing a new late investment.
EXPECTED_RECOVERY_TURNS = 2
CYCLE_SLACK_TURNS = 24
MIN_REQUIRED_TURNS = EXPECTED_RECOVERY_TURNS + CYCLE_SLACK_TURNS

_gate_count = 0


def reset_experiment():
    global _gate_count
    _gate_count = 0


def get_gate_count():
    return _gate_count


def _remaining_turns(obs):
    day = int(obs.get("day", 0)) if isinstance(obs, dict) else 0
    hour = int(obs.get("hour", 0)) if isinstance(obs, dict) else 0
    # If hour is unavailable, this remains conservative at the day boundary.
    hour = max(0, min(DAY_CALLS - 1, hour))
    return max(0, (TOTAL_DAYS - 1 - day) * DAY_CALLS + (DAY_CALLS - 1 - hour))


def _is_new_investment(action):
    return (
        isinstance(action, (list, tuple))
        and len(action) >= 1
        and isinstance(action[0], str)\n        and action[0].startswith("BUY_")
    )


def agent(obs):
    global _gate_count
    actions = v6.agent(obs)
    if _remaining_turns(obs) > MIN_REQUIRED_TURNS:
        return actions

    market = actions.get("market", []) if isinstance(actions, dict) else []
    if not any(_is_new_investment(a) for a in market):
        return actions

    revised = dict(actions)
    revised["market"] = [a for a in market if not _is_new_investment(a)]
    if revised["market"] != market:
        _gate_count += 1
    return revised
