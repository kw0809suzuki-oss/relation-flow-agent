#!/usr/bin/env python3
"""First observation batch for Relation Flow Pattern Mining v1.

Fresh sequential seeds are used. Pattern Bundles are constructed before the
terminal result is attached, so terminal outcome cannot define the patterns.
"""

import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import pattern_mining_observer as observer

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3264) % 2) for seed in range(3264, 3288))


def configure():
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    observer.reset()


def _flatten_numeric(prefix, obj, out):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out[prefix] = float(obj)
    elif isinstance(obj, dict):
        for key, value in sorted(obj.items()):
            _flatten_numeric(f"{prefix}.{key}" if prefix else str(key), value, out)


def _direction(delta):
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


def _rle(tokens):
    if not tokens:
        return []
    result = []
    start = 0
    current = tokens[0]
    for i, token in enumerate(tokens[1:], 1):
        if token != current:
            result.append({"direction": current, "start_step": start, "length": i - start})
            start, current = i, token
    result.append({"direction": current, "start_step": start, "length": len(tokens) - start})
    return result


def build_bundle(trace):
    snapshots = trace["day_snapshots"]
    series = {}
    for snap in snapshots:
        flat = {}
        for section in ("self", "opponent", "self_private_inventory", "market"):
            _flatten_numeric(section, snap.get(section, {}), flat)
        for key, value in flat.items():
            series.setdefault(key, []).append(value)

    patterns = {}
    transition_counts = Counter()
    cross_day_events = []
    for key, values in sorted(series.items()):
        directions = [_direction(b - a) for a, b in zip(values, values[1:])]
        runs = _rle(directions)
        transitions = Counter(f"{a}->{b}" for a, b in zip(directions, directions[1:]) if a != b)
        transition_counts.update(transitions)
        patterns[key] = {
            "start": values[0] if values else None,
            "end": values[-1] if values else None,
            "net": (values[-1] - values[0]) if len(values) >= 2 else 0.0,
            "direction_runs": runs,
            "transition_counts": dict(transitions),
        }

    if len(snapshots) >= 2:
        flats = []
        for snap in snapshots:
            flat = {}
            for section in ("self", "opponent", "self_private_inventory", "market"):
                _flatten_numeric(section, snap.get(section, {}), flat)
            flats.append(flat)
        keys = sorted(set().union(*(f.keys() for f in flats)))
        for i in range(1, len(flats)):
            changed = {key: _direction(flats[i].get(key, 0.0) - flats[i - 1].get(key, 0.0)) for key in keys}
            changed = {k: v for k, v in changed.items() if v != "flat"}
            cross_day_events.append({"from_day": snapshots[i - 1]["day"], "to_day": snapshots[i]["day"], "changed": changed})

    action_signatures = Counter(json.dumps(a, sort_keys=True, ensure_ascii=False) for a in trace["actions"])
    return {
        "schema": "relation-flow-pattern-bundle.v1",
        "constructed_without_terminal": True,
        "day_count": len(snapshots),
        "observed_dimensions": len(series),
        "series_patterns": patterns,
        "cross_day_events": cross_day_events,
        "global_transition_counts": dict(transition_counts),
        "action_profile": {"unique_actions": len(action_signatures), "top_signatures": action_signatures.most_common(12)},
    }


def play(seed, seat):
    configure()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = observer.agent
    env.run(players)
    # Bundle is frozen before reading terminal rewards.
    bundle = build_bundle(observer.get_trace())
    rewards = [state.reward for state in env.state]
    terminal = {
        "self": float(rewards[seat]),
        "opponent": float(rewards[1 - seat]),
        "margin": float(rewards[seat]) - float(rewards[1 - seat]),
        "win": float(rewards[seat]) > float(rewards[1 - seat]),
    }
    return {"seed": seed, "seat": seat, "pattern_bundle": bundle, "terminal": terminal}


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    summary = {
        "case_count": len(cases),
        "wins": sum(c["terminal"]["win"] for c in cases),
        "mean_margin": sum(c["terminal"]["margin"] for c in cases) / len(cases),
        "mean_observed_dimensions": sum(c["pattern_bundle"]["observed_dimensions"] for c in cases) / len(cases),
        "all_bundles_result_blind": all(c["pattern_bundle"]["constructed_without_terminal"] for c in cases),
    }
    result = {
        "schema": "kaggriculture.relation-flow-pattern-mining.v1.observation24",
        "external_goal": "improve terminal score through whole Relation Flow recognition and later intervention",
        "current_phase": "observe and extract multiple patterns; no control mapping",
        "cases": cases,
        "summary": summary,
        "runtime_inputs_excluded_from_pattern_construction": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "control_added": False,
        "causal_attribution": False,
    }
    Path("pattern_mining_v1_observation24.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("PATTERN_MINING_V1 " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
