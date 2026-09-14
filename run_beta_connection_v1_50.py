#!/usr/bin/env python3
"""Paired 50-seed connection test: beta-stop -> next-day reduced gate magnitude."""

import copy
import json
import os
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import beta_connection_agent_v1 as agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 3362) % 2) for seed in range(3362, 3412))


def configure(enabled):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    agent.set_control_enabled(enabled)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def play(seed, seat, enabled):
    configure(enabled)
    actions = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        action = agent.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {
        "score": score(rewards, seat),
        "actions": actions,
        "telemetry": agent.get_telemetry(),
        "trace": agent.get_trace(),
    }


def first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, False)
        candidate = play(seed, seat, True)
        delta = candidate["score"]["margin"] - baseline["score"]["margin"]
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": baseline["score"],
            "candidate": candidate["score"],
            "margin_delta": delta,
            "direction": "improved" if delta > 0 else "worsened" if delta < 0 else "equal",
            "first_action_difference": first_difference(candidate["actions"], baseline["actions"]),
            "action_difference_count": sum(x != y for x, y in zip(candidate["actions"], baseline["actions"])),
            "candidate_telemetry": candidate["telemetry"],
            "candidate_trace": candidate["trace"],
        })

    deltas = [r["margin_delta"] for r in rows]
    directions = Counter(r["direction"] for r in rows)
    summary = {
        "case_count": len(rows),
        "seed_range": "3362-3411",
        "mean_margin_delta": sum(deltas) / len(deltas),
        "median_margin_delta": sorted(deltas)[len(deltas)//2 - 1:len(deltas)//2 + 1],
        "baseline_wins": sum(r["baseline"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate"]["win"] for r in rows),
        "direction_counts": dict(directions),
        "largest_improvement": max(deltas),
        "largest_worsening": min(deltas),
        "action_difference_cases": sum(r["first_action_difference"] is not None for r in rows),
        "total_action_differences": sum(r["action_difference_count"] for r in rows),
        "beta_event_cases": sum(r["candidate_telemetry"]["beta_event_count"] > 0 for r in rows),
        "total_beta_events": sum(r["candidate_telemetry"]["beta_event_count"] for r in rows),
        "total_controlled_turns": sum(r["candidate_telemetry"]["controlled_turns"] for r in rows),
    }
    summary["win_delta"] = summary["candidate_wins"] - summary["baseline_wins"]

    result = {
        "schema": "kaggriculture.connection.beta-stop-next-day.v1.50",
        "question": "does a simple causal connection from confirmed beta-stop to reduced next-day gate magnitude improve terminal score?",
        "design_unit": {
            "observation": "frozen beta-stop: self active_tiles up->flat AND self COW up->flat on completed daily snapshots",
            "connection": "after confirmed beta-stop, set ORIGIN_GATE_MAGNITUDE 0.04 -> 0.02 for the following game day only",
            "default": "0.04",
        },
        "runtime_inputs_excluded": ["seed", "paired_difference", "terminal_reward", "future_state"],
        "terminal_used_to_define_connection": False,
        "native_origin_direction_preserved": True,
        "strong_origin_mutated": False,
        "cases": rows,
        "summary": summary,
    }
    out = Path("beta_connection_v1_50_3362_3411.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("BETA_CONNECTION_V1_50 " + json.dumps(summary, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
