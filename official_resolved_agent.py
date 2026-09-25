"""Candidate wrapper: current Battle body followed by Official World Resolver v0."""

import whole_flow_control_agent as body
import official_world_resolver as resolver

_STATS = {"turns": 0, "changed_turns": 0, "farmer_changes": 0, "hand_changes": 0, "market_changes": 0, "events": []}


def set_control_enabled(enabled):
    return body.set_control_enabled(enabled)


def set_probe_enabled(enabled):
    return body.set_probe_enabled(enabled)


def set_attribution_enabled(enabled):
    return body.set_attribution_enabled(enabled)


def reset_telemetry():
    global _STATS
    _STATS = {"turns": 0, "changed_turns": 0, "farmer_changes": 0, "hand_changes": 0, "market_changes": 0, "events": []}
    return body.reset_telemetry()


def get_telemetry():
    out = dict(body.get_telemetry())
    out.update({k: v for k, v in _STATS.items() if k != "events"})
    return out


def get_trace():
    return {"body": body.get_trace(), "official_resolver": [dict(x) for x in _STATS.get("events", [])]}


def agent(obs):
    candidate = body.agent(obs)
    resolved = resolver.resolve_action(obs, candidate)

    farmer_changed = candidate.get("farmer") != resolved.get("farmer")
    candidate_hands = list(candidate.get("hands", []))
    resolved_hands = list(resolved.get("hands", []))
    hand_changed_count = sum(a != b for a, b in zip(candidate_hands, resolved_hands))
    hand_changed_count += abs(len(candidate_hands) - len(resolved_hands))
    market_changed = candidate.get("market", []) != resolved.get("market", [])

    if farmer_changed or hand_changed_count or market_changed:
        _STATS["changed_turns"] += 1
        _STATS["events"].append({
            "turn": _STATS["turns"],
            "day": obs.get("day"),
            "hour": obs.get("hour"),
            "farmer_changed": bool(farmer_changed),
            "hand_changed_count": int(hand_changed_count),
            "market_changed": bool(market_changed),
            "candidate_market": candidate.get("market", []),
            "resolved_market": resolved.get("market", []),
            "candidate_farmer": candidate.get("farmer"),
            "resolved_farmer": resolved.get("farmer"),
            "candidate_hands": candidate_hands,
            "resolved_hands": resolved_hands,
        })
    _STATS["farmer_changes"] += int(farmer_changed)
    _STATS["hand_changes"] += int(hand_changed_count)
    _STATS["market_changes"] += int(market_changed)
    _STATS["turns"] += 1
    return resolved
