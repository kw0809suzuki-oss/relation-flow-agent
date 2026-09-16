"""Production Agent v6: maintenance-light Expansion Bridge.

Single front-side game-rule change over frozen v3:
- keep the same land / hands / livestock / crop economy
- keep the same two bridge targets
- reduce dedicated Expansion Bridge workers from 2 to 1

Goal: test whether the same production system can run with a lighter
maintenance allocation. Bundle / Relation / Flow remain observation-only.
"""

import production_agent_v3_expansion_bridge as base

BRIDGE_WORKERS = 1


def reset_telemetry():
    return base.reset_telemetry()


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v6_bridge1"] = {
        "bridge_workers": BRIDGE_WORKERS,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def agent(obs):
    previous = base.BRIDGE_WORKERS
    base.BRIDGE_WORKERS = BRIDGE_WORKERS
    try:
        return base.agent(obs)
    finally:
        base.BRIDGE_WORKERS = previous
