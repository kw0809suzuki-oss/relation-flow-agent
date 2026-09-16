"""Production Agent v5: top-practice cow scale candidate.

Frozen baseline: Production v3 Expansion Bridge.
Single design change only:
- keep the existing cow schedule through 8 cows
- add one late target step to 9 cows

No Bundle / Relation / Flow signal is read for runtime control.
"""

import production_agent_v1 as production_v1
import production_agent_v3_expansion_bridge as base

COW_TARGETS = ((5, 2), (9, 4), (14, 6), (20, 8), (24, 9))

_STATS = {
    "turns": 0,
}


def reset_telemetry():
    base.reset_telemetry()
    for k in _STATS:
        _STATS[k] = 0


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v5_cow9"] = {
        **_STATS,
        "cow_targets": [list(x) for x in COW_TARGETS],
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def agent(obs):
    previous_targets = production_v1.COW_TARGETS
    production_v1.COW_TARGETS = COW_TARGETS
    try:
        action = base.agent(obs)
        _STATS["turns"] += 1
        return action
    finally:
        production_v1.COW_TARGETS = previous_targets
