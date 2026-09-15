"""Full Strong Origin v2.2: bounded-pulse falsification candidate.

Question:
Does the v2.1 downside mainly come from repeated continuity-breaking overrides?

Design:
- keep Full v1 as the body
- keep the same feed-pressure guard and zero-detour fertilizer eligibility
- allow at most one fertilizer intervention episode per game day
- cap each episode at three action overrides (pickup -> move -> fertilize)
- after the episode ends, no more fertilizer overrides until the next day

This does not prove a cause. It is a falsification-oriented probe: if bounded
intervention still produces similar downside while genuinely firing, the
"continuity-break cost" hypothesis weakens.
"""

import copy

import full_strong_origin_v2_1_zero_detour as v21
import full_strong_origin_v1 as base

_STATS = {
    "turns": 0,
    "feed_pressure_turns": 0,
    "eligible_edge_turns": 0,
    "episodes_started": 0,
    "episode_overrides": 0,
    "pickup_actions": 0,
    "move_actions": 0,
    "fertilize_actions": 0,
    "skipped_day_locked": 0,
    "skipped_no_edge": 0,
}

_day = None
_day_episode_used = False
_episode_remaining = 0
_episode_hand = None


def reset_telemetry():
    global _day, _day_episode_used, _episode_remaining, _episode_hand
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0
    _day = None
    _day_episode_used = False
    _episode_remaining = 0
    _episode_hand = None


def get_telemetry():
    data = dict(base.get_telemetry())
    data["whole_v2_2"] = dict(_STATS)
    data["whole_v2_2"]["composition"] = "v2.1 zero-detour eligibility + one bounded intervention episode per day"
    return data


def _refresh_day(obs):
    global _day, _day_episode_used, _episode_remaining, _episode_hand
    day = obs.get("day")
    if day != _day:
        _day = day
        _day_episode_used = False
        _episode_remaining = 0
        _episode_hand = None


def _is_light(action):
    return bool(action) and action[0] in v21.ALLOWED_BASE_ACTIONS


def agent(obs):
    global _day_episode_used, _episode_remaining, _episode_hand
    _refresh_day(obs)
    action = copy.deepcopy(base.agent(obs))
    _STATS["turns"] += 1

    if v21._feed_pressure(obs):
        _STATS["feed_pressure_turns"] += 1
        _episode_remaining = 0
        _episode_hand = None
        return action

    me = obs["farms"][obs["player"]]
    private = obs["private"]
    hands = list(me.get("hands", []))
    inventories = list(private.get("inventories", []))
    shed = private.get("shed", {})
    targets = v21._fertilizer_targets(obs)
    if not hands or not targets:
        _STATS["skipped_no_edge"] += 1
        return action

    hand_actions = list(action.get("hands", []))
    while len(hand_actions) < len(hands):
        hand_actions.append(["PASS"])
    while len(inventories) < 1 + len(hands):
        inventories.append({})

    # Continue only the already-started bounded episode. Never switch hands.
    if _episode_remaining > 0 and _episode_hand is not None and _episode_hand < len(hands):
        i = _episode_hand
        if not _is_light(hand_actions[i]):
            _episode_remaining = 0
            _episode_hand = None
            return action
        pos = tuple(hands[i])
        if int(inventories[i + 1].get("FERTILIZER", 0)) > 0:
            target = v21._nearest(pos, targets)
            if target is not None and v21._distance(pos, target) <= 1:
                if pos == target:
                    hand_actions[i] = ["FERTILIZE"]
                    _STATS["fertilize_actions"] += 1
                    _episode_remaining = 0
                    _episode_hand = None
                else:
                    hand_actions[i] = v21._move_toward(pos, target)
                    _STATS["move_actions"] += 1
                    _episode_remaining -= 1
                _STATS["episode_overrides"] += 1
                action["hands"] = hand_actions
                return action
        _episode_remaining = 0
        _episode_hand = None
        return action

    if _day_episode_used:
        _STATS["skipped_day_locked"] += 1
        return action

    if int(shed.get("FERTILIZER", 0)) <= 0:
        _STATS["skipped_no_edge"] += 1
        return action

    board_size = len(me["tiles"])
    starters = []
    for i, base_action in enumerate(hand_actions):
        if not _is_light(base_action):
            continue
        pos = tuple(hands[i])
        if not v21._adjacent_shed(pos, board_size):
            continue
        target = v21._nearest(pos, targets)
        if target is not None and v21._distance(pos, target) <= 1:
            starters.append((i, pos, target))

    if not starters:
        _STATS["skipped_no_edge"] += 1
        return action

    i, _, _ = starters[0]
    _STATS["eligible_edge_turns"] += 1
    action["market"] = v21._retain_one_fertilizer(action.get("market", []), shed.get("FERTILIZER", 0))
    hand_actions[i] = ["PICKUP", "FERTILIZER", 1]
    action["hands"] = hand_actions

    _day_episode_used = True
    _episode_remaining = 2
    _episode_hand = i
    _STATS["episodes_started"] += 1
    _STATS["episode_overrides"] += 1
    _STATS["pickup_actions"] += 1
    return action
