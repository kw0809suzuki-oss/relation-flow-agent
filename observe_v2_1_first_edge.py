#!/usr/bin/env python3
"""Observer-only: compare the first Whole v2.1 intervention boundary.

Known from the paired result: all 50 cases first differ at turn 103.
This script replays the same cases and records only the pre-action State and
baseline/candidate actions at that boundary. Terminal outcome is attached only
after the boundary record is formed; it is not used by either agent.
"""

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

from kaggle_environments import make

import full_strong_origin_v1 as baseline_agent
import full_strong_origin_v2_1_zero_detour as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3662) % 2) for seed in range(3662, 3712))
BOUNDARY = 103


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1-seat])
    return {"self": own, "opponent": opp, "margin": own-opp}


def crop_counts(farm):
    out = Counter()
    active = 0
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT":
                active += 1
                out[tile.get("crop", "?")] += 1
    return active, dict(sorted(out.items()))


def snapshot(obs, base_action, cand_action):
    p = obs["player"]
    me = obs["farms"][p]
    opp = obs["farms"][1-p]
    private = obs["private"]
    active, crops = crop_counts(me)
    opp_active, opp_crops = crop_counts(opp)
    targets = candidate_agent._fertilizer_targets(obs)
    hands = [tuple(x) for x in me.get("hands", [])]
    inventories = list(private.get("inventories", []))

    diffs = []
    bh = list(base_action.get("hands", []))
    ch = list(cand_action.get("hands", []))
    n = max(len(bh), len(ch))
    for i in range(n):
        a = bh[i] if i < len(bh) else None
        b = ch[i] if i < len(ch) else None
        if a != b:
            pos = hands[i] if i < len(hands) else None
            inv = inventories[i+1] if i+1 < len(inventories) else {}
            nearest = candidate_agent._nearest(pos, targets) if pos is not None else None
            dist = candidate_agent._distance(pos, nearest) if pos is not None and nearest is not None else None
            diffs.append({
                "hand_index": i,
                "position": pos,
                "inventory": inv,
                "baseline_action": a,
                "candidate_action": b,
                "nearest_target": nearest,
                "target_distance": dist,
            })

    shed = private.get("shed", {})
    return {
        "turn": BOUNDARY,
        "day": obs.get("day"),
        "self_money": me.get("money"),
        "opponent_money": opp.get("money"),
        "self_land": me.get("land"),
        "self_active_plants": active,
        "self_crops": crops,
        "opponent_active_plants": opp_active,
        "opponent_crops": opp_crops,
        "shed": {k: shed.get(k, 0) for k in ("WHEAT", "FERTILIZER", "COW")},
        "feed_pressure": candidate_agent._feed_pressure(obs),
        "target_count": len(targets),
        "hand_positions": hands,
        "hand_differences": diffs,
        "market_equal": base_action.get("market", []) == cand_action.get("market", []),
        "baseline_market": base_action.get("market", []),
        "candidate_market": cand_action.get("market", []),
    }


def play(seed, seat, module, capture=False):
    module.reset_telemetry()
    record = None
    t = -1
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        nonlocal t, record
        t += 1
        if capture and t == BOUNDARY:
            # Both decisions are computed from the same observed State. Reset is
            # not needed here because telemetry is not an input to decisions.
            base_action = copy.deepcopy(baseline_agent.agent(copy.deepcopy(obs)))
            cand_action = copy.deepcopy(candidate_agent.agent(copy.deepcopy(obs)))
            record = snapshot(obs, base_action, cand_action)
            return cand_action
        return module.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return score(rewards, seat), record


def sig(row):
    r = row["boundary"]
    diffs = r["hand_differences"]
    action_pair = tuple((tuple(d.get("baseline_action") or []), tuple(d.get("candidate_action") or []), d.get("target_distance")) for d in diffs)
    return (
        r["day"], r["feed_pressure"], r["shed"]["FERTILIZER"], r["shed"]["WHEAT"],
        r["target_count"], action_pair, r["market_equal"],
    )


def main():
    rows = []
    for seed, seat in CASES:
        base_score, _ = play(seed, seat, baseline_agent, capture=False)
        cand_score, boundary = play(seed, seat, candidate_agent, capture=True)
        delta = cand_score["self"] - base_score["self"]
        rows.append({
            "seed": seed,
            "seat": seat,
            "self_delta": delta,
            "direction": "improved" if delta > 0 else "worsened" if delta < 0 else "equal",
            "boundary": boundary,
        })

    groups = defaultdict(Counter)
    for row in rows:
        groups[row["direction"]][str(sig(row))] += 1

    def aggregate(direction):
        subset = [r for r in rows if r["direction"] == direction]
        transitions = Counter()
        fert = Counter()
        wheat = Counter()
        targets = Counter()
        positions = Counter()
        market_equal = Counter()
        for row in subset:
            b = row["boundary"]
            fert[b["shed"]["FERTILIZER"]] += 1
            wheat[b["shed"]["WHEAT"]] += 1
            targets[b["target_count"]] += 1
            market_equal[b["market_equal"]] += 1
            for d in b["hand_differences"]:
                transitions[(str(d["baseline_action"]), str(d["candidate_action"]), d["target_distance"])] += 1
                positions[tuple(d["position"])] += 1
        return {
            "count": len(subset),
            "action_transitions": {str(k): v for k,v in transitions.most_common()},
            "shed_fertilizer": dict(sorted(fert.items())),
            "shed_wheat": dict(sorted(wheat.items())),
            "target_count": dict(sorted(targets.items())),
            "intervention_positions": {str(k): v for k,v in positions.most_common()},
            "market_equal": {str(k): v for k,v in market_equal.items()},
            "unique_boundary_signatures": len(groups[direction]),
        }

    summary = {
        "case_count": len(rows),
        "boundary": BOUNDARY,
        "first_action_difference_all_cases": True,
        "improved": aggregate("improved"),
        "worsened": aggregate("worsened"),
    }
    result = {
        "schema": "kaggriculture.v2-1-first-edge-observer.v1",
        "observer_only": True,
        "agent_mutated": False,
        "terminal_used_after_boundary_capture": True,
        "causal_attribution": False,
        "rows": rows,
        "summary": summary,
    }
    Path("v2_1_first_edge_observer_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("V2_1_FIRST_EDGE " + json.dumps(summary, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
