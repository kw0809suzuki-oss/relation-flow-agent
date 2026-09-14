#!/usr/bin/env python3
"""Shadow-only observer for the shared-world transition around turn 120->121.

Compares the five previously worsened seeds under the frozen G5+ROI baseline
and Full Strong Origin v1. No policy inputs are changed. The observer records
public farm state, market prices, unlocked shops, and the chosen action around
turns 119-122 so the shared-world transition can be compared directly.
"""

import copy
import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = ((3514, 0), (3528, 0), (3530, 0), (3554, 0), (3561, 1))
WINDOW = {119, 120, 121, 122}


def _plants(farm):
    out = Counter()
    active = 0
    for row in farm.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                active += 1
                out[tile.get("crop", "UNKNOWN")] += 1
    return active, dict(out)


def _public_farm(farm):
    active, crops = _plants(farm)
    animals = farm.get("animals", {})
    if isinstance(animals, dict):
        animal_counts = {str(k): len(v) if isinstance(v, list) else v for k, v in animals.items()}
    else:
        animal_counts = {}
    return {
        "money": float(farm.get("money", 0)),
        "hands": len(farm.get("hands", [])),
        "land": len(farm.get("unlocked_quadrants", [])),
        "active_plants": active,
        "crops": crops,
        "animals": animal_counts,
    }


def _telemetry_point(before, after):
    bt = before.get("turns", 0)
    at = after.get("turns", 0)
    bsum = before.get("mean_distortion", 0.0) * bt
    asum = after.get("mean_distortion", 0.0) * at
    distortion = asum - bsum if at > bt else None
    origin = None
    for name, count in after.get("origins", {}).items():
        if count > before.get("origins", {}).get(name, 0):
            origin = name
            break
    return {
        "origin": origin,
        "distortion": distortion,
        "distortion_trigger": after.get("distortion_trigger_turns", 0) > before.get("distortion_trigger_turns", 0),
        "crop_trigger": after.get("crop_trigger_turns", 0) > before.get("crop_trigger_turns", 0),
        "counter_active": after.get("counter_active_turns", 0) > before.get("counter_active_turns", 0),
    }


def _world(obs):
    market = obs.get("market", {})
    town = obs.get("town", {})
    prices = market.get("prices", {}) if isinstance(market, dict) else {}
    shops = town.get("unlocked_shops", []) if isinstance(town, dict) else []
    return {
        "day": obs.get("day"),
        "prices": {k: float(v) for k, v in prices.items() if isinstance(v, (int, float))},
        "shops": list(shops),
    }


def play(seed, seat, module):
    module.reset_telemetry()
    trace = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        turn = len(trace)
        before = module.get_telemetry()
        action = module.agent(obs)
        after = module.get_telemetry()
        if turn in WINDOW:
            trace.append({
                "turn": turn,
                "world": _world(obs),
                "self": _public_farm(obs["farms"][obs["player"]]),
                "opponent": _public_farm(obs["farms"][1 - obs["player"]]),
                "decision": _telemetry_point(before, after),
                "action": copy.deepcopy(action),
            })
        else:
            trace.append({"turn": turn})
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    return {x["turn"]: x for x in trace if x["turn"] in WINDOW}


def _numeric_delta(a, b):
    out = {}
    for key in sorted(set(a) | set(b)):
        av, bv = a.get(key), b.get(key)
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            out[key] = bv - av
    return out


def _state_delta(base, cand):
    return {
        "self": _numeric_delta(base["self"], cand["self"]),
        "opponent": _numeric_delta(base["opponent"], cand["opponent"]),
        "prices": _numeric_delta(base["world"]["prices"], cand["world"]["prices"]),
        "shops_equal": base["world"]["shops"] == cand["world"]["shops"],
    }


def main():
    rows = []
    for seed, seat in CASES:
        base = play(seed, seat, baseline_agent)
        cand = play(seed, seat, candidate_agent)
        rows.append({
            "seed": seed,
            "seat": seat,
            "turns": {
                str(t): {
                    "baseline": base[t],
                    "candidate": cand[t],
                    "candidate_minus_baseline": _state_delta(base[t], cand[t]),
                }
                for t in sorted(WINDOW)
            },
        })

    result = {
        "schema": "kaggriculture.full-v1-world-transition.v1",
        "question": "what shared-world and public-state changes distinguish Full v1 from baseline around the common turn 120->121 exit?",
        "cases": rows,
        "observer_only": True,
        "agent_mutated": False,
        "window": sorted(WINDOW),
        "runtime_inputs_excluded": ["seed_as_policy_input", "paired_difference_as_policy_input", "terminal_reward_as_policy_input", "future_state"],
    }
    Path("full_v1_world_transition.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    for row in rows:
        print("WORLD_TRANSITION", row["seed"], json.dumps(row["turns"]["120"]["candidate_minus_baseline"], separators=(",", ":")), json.dumps(row["turns"]["121"]["candidate_minus_baseline"], separators=(",", ":")))


if __name__ == "__main__":
    main()
