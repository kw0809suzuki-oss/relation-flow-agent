#!/usr/bin/env python3
"""Shadow-only exit observer for Full Strong Origin v1.

Purpose:
- keep baseline and Full v1 behavior unchanged
- inspect only the five previously worsened paired seeds
- locate the earliest turn where the opponent-side observable/reward diverges upward
- attach the immediately preceding Full v1 Origin/distortion/crop-trigger state

This observer does not alter actions and does not use results as runtime inputs.
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
    b_orig = before.get("origins", {})
    a_orig = after.get("origins", {})
    for name, count in a_orig.items():
        if count > b_orig.get(name, 0):
            origin = name
            break

    return {
        "origin": origin,
        "distortion": distortion,
        "distortion_trigger": after.get("distortion_trigger_turns", 0) > before.get("distortion_trigger_turns", 0),
        "crop_trigger": after.get("crop_trigger_turns", 0) > before.get("crop_trigger_turns", 0),
        "counter_active": after.get("counter_active_turns", 0) > before.get("counter_active_turns", 0),
    }


def play(seed, seat, module):
    module.reset_telemetry()
    trace = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        before = module.get_telemetry()
        snapshot = {
            "turn": len(trace),
            "day": obs.get("day"),
            "self": _public_farm(obs["farms"][obs["player"]]),
            "opponent": _public_farm(obs["farms"][1 - obs["player"]]),
        }
        action = module.agent(obs)
        after = module.get_telemetry()
        snapshot["decision"] = _telemetry_point(before, after)
        snapshot["action"] = copy.deepcopy(action)
        trace.append(snapshot)
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)

    rewards = []
    for step_index, step in enumerate(env.steps):
        item = {"step": step_index, "self": None, "opponent": None}
        try:
            item["self"] = step[seat].get("reward") if isinstance(step[seat], dict) else step[seat].reward
            item["opponent"] = step[1 - seat].get("reward") if isinstance(step[1 - seat], dict) else step[1 - seat].reward
        except Exception:
            pass
        rewards.append(item)
    return {"trace": trace, "rewards": rewards}


def _first_positive_reward_delta(base, cand):
    for b, c in zip(base["rewards"], cand["rewards"]):
        br, cr = b.get("opponent"), c.get("opponent")
        if isinstance(br, (int, float)) and isinstance(cr, (int, float)) and cr - br > 0:
            return {"step": c["step"], "baseline": br, "candidate": cr, "delta": cr - br}
    return None


def _first_positive_money_delta(base, cand):
    for b, c in zip(base["trace"], cand["trace"]):
        delta = c["opponent"]["money"] - b["opponent"]["money"]
        if delta > 0:
            return {"turn": c["turn"], "day": c["day"], "baseline": b["opponent"]["money"], "candidate": c["opponent"]["money"], "delta": delta}
    return None


def _context(trace, turn):
    if turn is None:
        return None
    i = max(0, min(turn, len(trace) - 1))
    prev = trace[i - 1] if i > 0 else None
    cur = trace[i]
    return {"previous": prev, "current": cur}


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, baseline_agent)
        candidate = play(seed, seat, candidate_agent)
        reward_exit = _first_positive_reward_delta(baseline, candidate)
        money_exit = _first_positive_money_delta(baseline, candidate)
        turn = money_exit["turn"] if money_exit else None
        rows.append({
            "seed": seed,
            "seat": seat,
            "first_positive_opponent_reward_delta": reward_exit,
            "first_positive_opponent_money_delta": money_exit,
            "candidate_context_at_money_exit": _context(candidate["trace"], turn),
            "baseline_context_at_money_exit": _context(baseline["trace"], turn),
            "reward_points_with_values": sum(1 for x in candidate["rewards"] if isinstance(x.get("opponent"), (int, float))),
            "turn_count": len(candidate["trace"]),
        })

    result = {
        "schema": "kaggriculture.full-v1-opponent-exit-shadow.v1",
        "question": "where does the opponent-side upward divergence first become observable in the five previously worsened Full v1 pairs?",
        "cases": rows,
        "observer_only": True,
        "agent_mutated": False,
        "runtime_inputs_excluded": ["seed_as_policy_input", "paired_difference_as_policy_input", "terminal_reward_as_policy_input", "future_state"],
        "interpretation_note": "reward divergence is preferred when intermediate rewards exist; opponent money divergence is an observable flow marker, not by itself a causal explanation of terminal score.",
    }
    Path("full_v1_opponent_exit_shadow.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("FULL_V1_OPPONENT_EXIT_SHADOW " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
