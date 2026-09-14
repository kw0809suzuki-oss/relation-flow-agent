#!/usr/bin/env python3
"""Shadow-only opponent-action observer at the day-5 exit boundary.

Compares baseline vs Full v1 for the five previously worsened seeds.
No policy behavior is changed. The pinned opponent is imported and wrapped only
so its emitted actions can be recorded alongside turn-120/121 public state.
"""

import copy
import importlib.util
import json
from pathlib import Path

from kaggle_environments import make

import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH = "opponents/seyamalam_v21.py"
CASES = ((3514, 0), (3528, 0), (3530, 0), (3554, 0), (3561, 1))
WATCH = {119, 120, 121, 122}


def load_opponent():
    spec = importlib.util.spec_from_file_location("seyamalam_v21_shadow", OPPONENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "agent", None)
    if fn is None:
        raise RuntimeError("Pinned opponent module has no agent()")
    return fn


def farm_state(farm):
    plants = 0
    crops = {}
    for row in farm.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                plants += 1
                crop = tile.get("crop", "UNKNOWN")
                crops[crop] = crops.get(crop, 0) + 1
    return {
        "money": float(farm.get("money", 0)),
        "hands": len(farm.get("hands", [])),
        "land": len(farm.get("unlocked_quadrants", [])),
        "plants": plants,
        "crops": crops,
    }


def play(seed, seat, self_module):
    self_module.reset_telemetry()
    opponent_fn = load_opponent()
    opp_trace = []
    self_trace = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def self_wrapped(obs):
        turn = len(self_trace)
        action = self_module.agent(obs)
        if turn in WATCH:
            self_trace.append({
                "turn": turn,
                "day": obs.get("day"),
                "self": farm_state(obs["farms"][obs["player"]]),
                "opponent": farm_state(obs["farms"][1 - obs["player"]]),
                "market_prices": copy.deepcopy(obs.get("market", {}).get("prices", {})),
                "shops": copy.deepcopy(obs.get("town", {}).get("unlocked_shops", [])),
                "action": copy.deepcopy(action),
            })
        else:
            self_trace.append({"turn": turn})
        return action

    opp_turn = 0
    def opp_wrapped(obs):
        nonlocal opp_turn
        action = opponent_fn(obs)
        if opp_turn in WATCH:
            opp_trace.append({
                "turn": opp_turn,
                "day": obs.get("day"),
                "self": farm_state(obs["farms"][obs["player"]]),
                "opponent": farm_state(obs["farms"][1 - obs["player"]]),
                "market_prices": copy.deepcopy(obs.get("market", {}).get("prices", {})),
                "shops": copy.deepcopy(obs.get("town", {}).get("unlocked_shops", [])),
                "action": copy.deepcopy(action),
            })
        opp_turn += 1
        return action

    players = [opp_wrapped, opp_wrapped]
    players[seat] = self_wrapped
    env.run(players)
    return {"self": [x for x in self_trace if x.get("turn") in WATCH], "opponent": opp_trace}


def by_turn(rows):
    return {str(x["turn"]): x for x in rows}


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, baseline_agent)
        candidate = play(seed, seat, candidate_agent)
        bopp, copp = by_turn(baseline["opponent"]), by_turn(candidate["opponent"])
        action_diffs = {}
        for turn in sorted(WATCH):
            key = str(turn)
            ba = bopp.get(key, {}).get("action")
            ca = copp.get(key, {}).get("action")
            action_diffs[key] = {
                "different": ba != ca,
                "baseline": ba,
                "candidate": ca,
            }
        rows.append({
            "seed": seed,
            "seat": seat,
            "opponent_action_diffs": action_diffs,
            "baseline_opponent_trace": baseline["opponent"],
            "candidate_opponent_trace": candidate["opponent"],
            "baseline_self_trace": baseline["self"],
            "candidate_self_trace": candidate["self"],
        })

    result = {
        "schema": "kaggriculture.full-v1-opponent-action-shadow.v1",
        "question": "does the pinned opponent emit a different action at/around turn 120 when facing Full v1 rather than baseline?",
        "cases": rows,
        "observer_only": True,
        "agent_mutated": False,
    }
    Path("full_v1_opponent_action_shadow.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    compact = []
    for row in rows:
        compact.append({"seed": row["seed"], "diffs": {t: v["different"] for t, v in row["opponent_action_diffs"].items()}})
    print("FULL_V1_OPPONENT_ACTION_SHADOW " + json.dumps(compact, separators=(",", ":")))


if __name__ == "__main__":
    main()
