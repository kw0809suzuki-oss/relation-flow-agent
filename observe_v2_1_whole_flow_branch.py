#!/usr/bin/env python3
"""Observer-only Whole Flow branch detector for Whole v2.1.

Goal:
- do NOT trace individual causes after turn 103
- represent the observable whole State as one numeric vector
- compare 50 candidate-minus-Full-v1 trajectories without terminal labels
- find the earliest point where the trajectories form a clearly separated,
  persistent 2..5-way grouping
- only after the grouping is fixed, overlay terminal self-score direction

This is a structure observer, not a causal attribution tool.
"""

import copy
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as baseline_agent
import full_strong_origin_v2_1_zero_detour as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3662) % 2) for seed in range(3662, 3712))
START_TURN = 103
K_VALUES = (2, 3, 4, 5)
PERSIST_TURNS = 5
MIN_SILHOUETTE = 0.35
MIN_MEMBERSHIP_STABILITY = 0.80


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1-seat])
    return {"self": own, "opponent": opp, "margin": own - opp}


def _num(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _crop_code(name):
    return {None: 0.0, "WHEAT": 1.0, "MELON": 2.0, "STRAWBERRY": 3.0}.get(name, 4.0)


def _kind_code(name):
    return {None: 0.0, "EMPTY": 0.0, "PLANT": 1.0, "PASTURE": 2.0}.get(name, 3.0)


def whole_vector(obs):
    """Broad observable State vector; components are not interpreted here."""
    p = obs["player"]
    farms = obs.get("farms", [])
    me = farms[p]
    opp = farms[1-p]
    private = obs.get("private", {})
    out = [_num(obs.get("day", 0))]

    for farm in (me, opp):
        out.extend([
            _num(farm.get("money", 0)),
            _num(farm.get("land", 0)),
        ])
        for hand in farm.get("hands", []):
            if isinstance(hand, (list, tuple)) and len(hand) >= 2:
                out.extend([_num(hand[0]), _num(hand[1])])
        for row in farm.get("tiles", []):
            for tile in row:
                if not isinstance(tile, dict):
                    out.extend([0.0] * 7)
                    continue
                out.extend([
                    _kind_code(tile.get("kind")),
                    _crop_code(tile.get("crop")),
                    _num(tile.get("planted_day", -1)),
                    _num(tile.get("fertilized_until_day", -1)),
                    1.0 if tile.get("animal") == "COW" else 0.0,
                    _num(tile.get("watered_until_day", -1)),
                    _num(tile.get("harvestable", 0)),
                ])

    shed = private.get("shed", {})
    for key in ("WHEAT", "MELON", "STRAWBERRY", "FERTILIZER", "COW"):
        out.append(_num(shed.get(key, 0)))
    for inv in private.get("inventories", []):
        for key in ("WHEAT", "MELON", "STRAWBERRY", "FERTILIZER", "COW"):
            out.append(_num(inv.get(key, 0)))

    market = obs.get("market", {})
    if isinstance(market, dict):
        for key in sorted(market):
            item = market[key]
            if isinstance(item, dict):
                out.extend([_num(item.get("price", 0)), _num(item.get("inventory", 0))])
    return out


def play(seed, seat, module):
    module.reset_telemetry()
    states = []
    t = -1
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        nonlocal t
        t += 1
        if t >= START_TURN:
            states.append((t, whole_vector(copy.deepcopy(obs))))
        return module.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return score(rewards, seat), states


def subtract(a, b):
    n = max(len(a), len(b))
    return [(a[i] if i < len(a) else 0.0) - (b[i] if i < len(b) else 0.0) for i in range(n)]


def standardize(vectors):
    if not vectors:
        return []
    dims = max(len(v) for v in vectors)
    padded = [v + [0.0] * (dims-len(v)) for v in vectors]
    means = []
    scales = []
    for j in range(dims):
        col = [v[j] for v in padded]
        means.append(statistics.mean(col))
        sd = statistics.pstdev(col)
        scales.append(sd if sd > 1e-9 else 1.0)
    return [[(v[j]-means[j])/scales[j] for j in range(dims)] for v in padded]


def dist(a, b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def kmeans(points, k, rounds=30):
    # Deterministic farthest-first seeds; no result-label influence.
    centers = [points[0][:]]
    while len(centers) < k:
        idx = max(range(len(points)), key=lambda i: min(dist(points[i], c) for c in centers))
        centers.append(points[idx][:])
    labels = [0] * len(points)
    for _ in range(rounds):
        new_labels = [min(range(k), key=lambda j: dist(p, centers[j])) for p in points]
        if new_labels == labels and _ > 0:
            break
        labels = new_labels
        new_centers = []
        for j in range(k):
            members = [p for p,l in zip(points, labels) if l == j]
            if not members:
                new_centers.append(centers[j])
            else:
                new_centers.append([statistics.mean(vals) for vals in zip(*members)])
        centers = new_centers
    return labels


def silhouette(points, labels):
    groups = defaultdict(list)
    for i,l in enumerate(labels):
        groups[l].append(i)
    if len(groups) < 2 or any(len(v) < 2 for v in groups.values()):
        return -1.0
    vals = []
    for i,p in enumerate(points):
        own = groups[labels[i]]
        a = statistics.mean(dist(p, points[j]) for j in own if j != i)
        b = min(statistics.mean(dist(p, points[j]) for j in idxs) for l,idxs in groups.items() if l != labels[i])
        vals.append((b-a)/max(a,b) if max(a,b) > 1e-12 else 0.0)
    return statistics.mean(vals)


def partition_pairs(labels):
    return {(i,j): labels[i] == labels[j] for i in range(len(labels)) for j in range(i+1,len(labels))}


def stability(a, b):
    pa, pb = partition_pairs(a), partition_pairs(b)
    if not pa:
        return 1.0
    return sum(pa[k] == pb[k] for k in pa) / len(pa)


def main():
    trajectories = []
    terminal = []
    for seed, seat in CASES:
        bs, bstates = play(seed, seat, baseline_agent)
        cs, cstates = play(seed, seat, candidate_agent)
        bmap = dict(bstates)
        cmap = dict(cstates)
        common = sorted(set(bmap) & set(cmap))
        trajectories.append({t: subtract(cmap[t], bmap[t]) for t in common})
        delta = cs["self"] - bs["self"]
        terminal.append({
            "seed": seed,
            "seat": seat,
            "self_delta": delta,
            "direction": "improved" if delta > 0 else "worsened" if delta < 0 else "equal",
        })

    common_turns = sorted(set.intersection(*(set(t.keys()) for t in trajectories)))
    scans = []
    labels_by_turn = {}
    for t in common_turns:
        points = standardize([tr[t] for tr in trajectories])
        choices = []
        for k in K_VALUES:
            labels = kmeans(points, k)
            sil = silhouette(points, labels)
            sizes = sorted(Counter(labels).values(), reverse=True)
            choices.append((sil, k, labels, sizes))
        sil, k, labels, sizes = max(choices, key=lambda x: x[0])
        labels_by_turn[t] = labels
        scans.append({"turn": t, "k": k, "silhouette": sil, "cluster_sizes": sizes})

    boundary = None
    boundary_k = None
    boundary_labels = None
    for idx, row in enumerate(scans):
        if row["silhouette"] < MIN_SILHOUETTE:
            continue
        window = scans[idx:idx+PERSIST_TURNS]
        if len(window) < PERSIST_TURNS:
            break
        if any(w["silhouette"] < MIN_SILHOUETTE or w["k"] != row["k"] for w in window):
            continue
        base_labels = labels_by_turn[row["turn"]]
        stabs = [stability(base_labels, labels_by_turn[w["turn"]]) for w in window[1:]]
        if stabs and min(stabs) >= MIN_MEMBERSHIP_STABILITY:
            boundary = row["turn"]
            boundary_k = row["k"]
            boundary_labels = base_labels
            break

    overlay = None
    if boundary is not None:
        grouped = defaultdict(Counter)
        deltas = defaultdict(list)
        for label, term in zip(boundary_labels, terminal):
            grouped[label][term["direction"]] += 1
            deltas[label].append(term["self_delta"])
        overlay = {
            str(label): {
                "count": len(deltas[label]),
                "terminal_direction": dict(grouped[label]),
                "mean_self_delta": statistics.mean(deltas[label]),
            }
            for label in sorted(deltas)
        }

    summary = {
        "case_count": len(CASES),
        "start_turn": START_TURN,
        "boundary": boundary,
        "boundary_k": boundary_k,
        "detector": {
            "k_values": list(K_VALUES),
            "persistence_turns": PERSIST_TURNS,
            "min_silhouette": MIN_SILHOUETTE,
            "min_membership_stability": MIN_MEMBERSHIP_STABILITY,
            "terminal_labels_used_for_detection": False,
        },
        "terminal_overlay": overlay,
        "interpretation_gate": (
            "persistent whole-flow branch observed" if boundary is not None
            else "no single persistent early whole-flow branch observed under the fixed detector"
        ),
    }
    result = {
        "schema": "kaggriculture.v2-1-whole-flow-branch-observer.v1",
        "observer_only": True,
        "agent_mutated": False,
        "causal_attribution": False,
        "summary": summary,
        "scan": scans,
        "terminal": terminal,
    }
    Path("v2_1_whole_flow_branch_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("V2_1_WHOLE_FLOW_BRANCH " + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
