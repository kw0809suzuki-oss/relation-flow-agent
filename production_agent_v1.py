"""Production Agent v1.

Front side only: play Kaggriculture as a production game.
- keep the established Full Strong Origin v1 economic body
- keep the livestock revenue loop
- carry more feed per trip to reduce feed interruption

Bundle / Relation / Flow are not read here and do not control actions.
They remain external observation axes only.
"""

import full_strong_origin_v1 as base

COW_TARGETS = ((5, 2), (9, 4), (14, 6), (20, 8))
FEED_CARRY = 5


def reset_telemetry():
    return base.reset_telemetry()


def get_telemetry():
    data = dict(base.get_telemetry())
    data["production_v1"] = {
        "cow_targets": [list(x) for x in COW_TARGETS],
        "feed_carry": FEED_CARRY,
        "bundle_used_for_control": False,
        "relation_used_for_control": False,
        "flow_used_for_control": False,
    }
    return data


def agent(obs):
    previous_targets = base.COW_TARGETS
    previous_feed = base.FEED_CARRY
    base.COW_TARGETS = COW_TARGETS
    base.FEED_CARRY = FEED_CARRY
    try:
        return base.agent(obs)
    finally:
        base.COW_TARGETS = previous_targets
        base.FEED_CARRY = previous_feed
