#!/usr/bin/env python3
"""Fresh-seed validation for fixed Relation Flow components.

The component definitions are frozen from the earlier 3264-3287 observation batch.
This script only asks whether those definitions reappear on unseen seeds 3288-3311.
Terminal is attached after bundle construction and is not used to define components.
"""

import json
from collections import Counter
from pathlib import Path

from run_pattern_mining_v1 import play

CASES = tuple((seed, (seed - 3288) % 2) for seed in range(3288, 3312))


def expand_directions(pattern):
    out = []
    for run in pattern.get("direction_runs", []):
        out.extend([run["direction"]] * int(run["length"]))
    return out


def transitions(pattern):
    dirs = expand_directions(pattern)
    return [(dirs[i - 1], dirs[i]) for i in range(1, len(dirs))]


def relation(a, b):
    rank = {"down": -1, "flat": 0, "up": 1}
    d = rank[a] - rank[b]
    return "self" if d > 0 else "opponent" if d < 0 else "parallel"


def relation_series(bundle, self_key, opp_key):
    a = expand_directions(bundle["series_patterns"][self_key])
    b = expand_directions(bundle["series_patterns"][opp_key])
    return [relation(x, y) for x, y in zip(a, b)]


def component_events(bundle):
    p = bundle["series_patterns"]
    t_melon_price = transitions(p["market.prices.MELON"])
    t_melon_inv = transitions(p["market.inventory.MELON"])
    t_opp_active = transitions(p["opponent.active_tiles"])
    t_self_active = transitions(p["self.active_tiles"])
    t_self_cow = transitions(p["self.animals.COW"])

    active_rel = relation_series(bundle, "self.active_tiles", "opponent.active_tiles")
    cow_rel = relation_series(bundle, "self.animals.COW", "opponent.animals.COW")

    alpha_slow = []
    alpha_restart = []
    beta_stop = []

    n = min(len(t_melon_price), len(t_melon_inv), len(t_opp_active))
    for i in range(n):
        if t_melon_price[i] == ("up", "down") and t_melon_inv[i] == ("down", "up"):
            if t_opp_active[i] == ("up", "flat"):
                alpha_slow.append(i + 1)
            elif t_opp_active[i] == ("flat", "up"):
                alpha_restart.append(i + 1)

    n = min(len(t_self_active), len(t_self_cow))
    for i in range(n):
        if t_self_active[i] == ("up", "flat") and t_self_cow[i] == ("up", "flat"):
            beta_stop.append(i + 1)

    def rel_window(series, step):
        vals = []
        for off in (-1, 0, 1, 2):
            j = step + off
            vals.append(series[j] if 0 <= j < len(series) else None)
        return vals

    return {
        "alpha_slowdown": [{"step": s, "active_relation": rel_window(active_rel, s)} for s in alpha_slow],
        "alpha_restart": [{"step": s, "active_relation": rel_window(active_rel, s)} for s in alpha_restart],
        "beta_stop": [{"step": s, "active_relation": rel_window(active_rel, s), "cow_relation": rel_window(cow_rel, s)} for s in beta_stop],
    }


def summarize(cases):
    counts = Counter()
    traj = Counter()
    shapes = Counter()
    for c in cases:
        ev = c["fixed_component_events"]
        for name, rows in ev.items():
            counts[name] += len(rows)
            if rows:
                traj[name] += 1
        for row in ev["alpha_slowdown"]:
            r = row["active_relation"]
            if len(r) >= 3 and r[0] == "self" and r[1] == "opponent":
                shapes["alpha_slow_self_to_opponent"] += 1
            if r == ["parallel", "self", "opponent", "opponent"]:
                shapes["alpha_slow_parallel_self_opp_opp"] += 1
        for row in ev["alpha_restart"]:
            r = row["active_relation"]
            if len(r) >= 3 and r[:3] == ["parallel", "opponent", "opponent"]:
                shapes["alpha_restart_parallel_opp_opp"] += 1
        for row in ev["beta_stop"]:
            r = row["active_relation"]
            if len(r) >= 3 and r[0] != "opponent" and r[1] == "opponent" and r[2] == "opponent":
                shapes["beta_stop_nonopp_opp_opp"] += 1
    return {
        "case_count": len(cases),
        "event_counts": dict(counts),
        "trajectory_counts": dict(traj),
        "relation_shape_counts": dict(shapes),
    }


def main():
    cases = []
    for seed, seat in CASES:
        c = play(seed, seat)
        c["fixed_component_events"] = component_events(c["pattern_bundle"])
        cases.append(c)

    result = {
        "schema": "kaggriculture.relation-flow-fixed-components.validation24.v1",
        "source_component_batch": "3264-3287",
        "validation_seed_range": "3288-3311",
        "definitions_frozen_before_validation": True,
        "terminal_used_to_define_components": False,
        "control_added": False,
        "cases": cases,
        "summary": summarize(cases),
    }
    Path("pattern_validation_v1_3288_3311.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("FIXED_COMPONENT_VALIDATION " + json.dumps(result["summary"], separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
