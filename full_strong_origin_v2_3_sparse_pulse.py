"""Full Strong Origin v2.3: sparse bounded-pulse probe.

Purpose:
Reduce only intervention frequency while preserving v2.2 intervention content.
This is a short-loop probe for the relation between intervention dose and terminal score.

Design:
- Full v1 remains the body.
- Same zero-detour eligibility as v2.2.
- Same bounded episode: pickup -> optional move -> fertilize, max 3 overrides.
- New: after an episode starts, no new episode may start until at least 2 game days later.

No causal attribution is assumed.
"""

import copy

import full_strong_origin_v2_1_zero_detour as v21
import full_strong_origin_v1 as base

MIN_DAY_GAP = 2

_STATS = {
    "turns": 0,
    "feed_pressure_turns": 0,
    "eligible_edge_turns": 0,
    "episodes_started": 0,
    "episode_overrides": 0,
    "pickup_actions": 0,
    "move_actions": 0,
    "fertilize_actions": 0,
    "skipped_cooldown": 0,
    "skipped_no_edge": 0,
}

_last_episode_day = None
_episode_remaining = 0
_episode_hand = None


def reset_telemetry():
    global _last_episode_day, _episode_remaining, _episode_hand
    base.reset_telemetry()
    for key in _STATS:
        _STATS[key] = 0
    _last_episode_day = None
    _episode_remaining = 0
    _episode_hand = None


def get_telemetry():
    data = dict(base.get_telemetry())
    data["whole_v2_3"] = dict(_STATS)
    data["whole_v2_3"]["min_day_gap"] = MIN_DAY_GAP
    data["whole_v2_3"]["composition"] = "v2.2 bounded pulse + two-day start cooldown"
    return data


def _is_light(action):
    return bool(action) and action[0] in v21.ALLOWED_BASE_ACTIONS


def agent(obs):
    global _last_episode_day, _episode_remaining, _episode_hand
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

    day = int(obs.get("day", 0))
    if _last_episode_day is not None and day - _last_episode_day < MIN_DAY_GAP:
        _STATS["skipped_cooldown"] += 1
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

    _last_episode_day = day
    _episode_remaining = 2
    _episode_hand = i
    _STATS["episodes_started"] += 1
    _STATS["episode_overrides"] += 1
    _STATS["pickup_actions"] += 1
    return action
