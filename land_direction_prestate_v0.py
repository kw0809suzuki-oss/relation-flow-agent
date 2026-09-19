#!/usr/bin/env python3
"""LAND Direction Gate pre-intervention observer v0.

Question:
Can terminal self sign after first BUY_LAND suppression be separated using
only conditions visible before the intervention?

Scope is deliberately narrow:
- fresh10 only
- pre-intervention public/basic state only
- no internal scores / no post-hoc sequence mining
"""

import json
import os
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import land_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT
CASES = [(4502+i, i%2) for i in range(10)]


def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()


def count_animals(farm):
    count = 0
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("animal"):
                count += 1
    return count


def prestate(obs):
    p = int(obs["player"])
    me = obs["farms"][p]
    tiles = me.get("tiles", []) or []
    unlocked = occupied = empty = 0
    for row in tiles:
        for tile in row or []:
            if tile == "LOCKED":
                continue
            unlocked += 1
            if tile is None:
                empty += 1
            else:
                occupied += 1
    return {
        "day": int(obs.get("day", 0)),
        "money": float(me.get("money", 0) or 0),
        "land": len(me.get("unlocked_quadrants", []) or []),
        "hands": len(me.get("hands", []) or []),
        "animals": count_animals(me),
        "unlocked_tiles": unlocked,
        "occupied_tiles": occupied,
        "empty_tiles": empty,
        "occupancy": round((occupied / unlocked) if unlocked else 1.0, 6),
    }


def play_baseline(seed, seat):
    configure()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = baseline.agent
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return rewards[seat]


def play_candidate(seed, seat):
    configure()
    candidate.reset_experiment()
    captured = {"pre": None}

    def wrapped(obs):
        # Capture state immediately before the first native BUY_LAND is suppressed.
        before_count = len(candidate.get_activations())
        state = prestate(obs)
        action = candidate.agent(obs)
        after_count = len(candidate.get_activations())
        if captured["pre"] is None and before_count == 0 and after_count == 1:
            captured["pre"] = state
        return action

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = wrapped
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return rewards[seat], captured["pre"]


def main():
    rows = []
    for seed, seat in CASES:
        b = play_baseline(seed, seat)
        c, pre = play_candidate(seed, seat)
        diff = c - b
        rows.append({
            "seed": seed,
            "seat": seat,
            "class": "improved" if diff > 0 else "worsened" if diff < 0 else "equal",
            "self_diff": diff,
            "pre": pre,
        })

    fields = ["day","money","land","hands","animals","unlocked_tiles","occupied_tiles","empty_tiles","occupancy"]
    separators = {}
    improved = [r for r in rows if r["class"] == "improved"]
    worsened = [r for r in rows if r["class"] == "worsened"]

    for field in fields:
        iv = [r["pre"][field] for r in improved if r["pre"] is not None]
        wv = [r["pre"][field] for r in worsened if r["pre"] is not None]
        if iv and wv:
            separators[field] = {
                "improved_values": iv,
                "worsened_values": wv,
                "exact_sets_disjoint": set(iv).isdisjoint(set(wv)),
                "improved_range": [min(iv), max(iv)],
                "worsened_range": [min(wv), max(wv)],
                "ranges_disjoint": max(iv) < min(wv) or max(wv) < min(iv),
            }

    out = {
        "schema": "land-direction-prestate.v0",
        "question": "Can pre-intervention visible state separate terminal self sign?",
        "cases": rows,
        "fields": separators,
        "boundary": "Direction Gate only. No internal-state mining or post-intervention rescue conditions.",
    }

    with open("land_direction_prestate_v0.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
        f.write("\n")

    compact = {
        k: {
            "exact_sets_disjoint": v["exact_sets_disjoint"],
            "ranges_disjoint": v["ranges_disjoint"],
            "improved_range": v["improved_range"],
            "worsened_range": v["worsened_range"],
        }
        for k,v in separators.items()
    }
    print("LAND_DIRECTION_PRESTATE_FIELDS "+json.dumps(compact,separators=(",",":")))
    print("LAND_DIRECTION_PRESTATE_ROWS "+json.dumps(rows,separators=(",",":")))


if __name__ == "__main__":
    main()
