"""Production v3 with the previously stronger fixed feed carry restored.

Only one change relative to production_agent_v3_expansion_bridge:
- FEED_CARRY: 5 -> 4

All v2/v3 capacity and expansion bridge behavior remains unchanged.
Bundle / Relation / Flow remain observation-only and do not control actions.
"""

import production_agent_v1 as production_v1
import production_agent_v3_expansion_bridge as base

FEED_CARRY = 4


def reset_telemetry():
    return base.reset_telemetry()


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v3_feed4"] = {
        "feed_carry": FEED_CARRY,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def agent(obs):
    previous = production_v1.FEED_CARRY
    production_v1.FEED_CARRY = FEED_CARRY
    try:
        return base.agent(obs)
    finally:
        production_v1.FEED_CARRY = previous
