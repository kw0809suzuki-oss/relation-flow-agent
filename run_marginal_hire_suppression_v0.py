#!/usr/bin/env python3
"""Paired fresh20 Battle for Marginal HIRE Suppression v0."""

import copy
import json
import os
from pathlib import Path
from statistics import median

from kaggle_environments import make

import g17_agent as baseline_agent
import marginal_hire_suppression_v0 as candidate_agent

OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((seed, (seed - 5102) % 2) for seed in range(5102, 5122))


def configure(agent):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "0"
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1 - seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def play(seed, seat, agent):
    configure(agent)
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
    }


def summarize(rows, key):
    vals = [r["delta"][key] for r in rows]
    return {
        "improved": sum(v > 0 for v in vals),
        "worsened": sum(v < 0 for v in vals),
        "equal": sum(v == 0 for v in vals),
        "mean": sum(vals) / len(vals),
        "median": median(vals),
        "min": min(vals),
        "max": max(vals),
    }


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, baseline_agent)
        candidate = play(seed, seat, candidate_agent)
        delta = {
            k: candidate["score"][k] - baseline["score"][k]
            for k in ("self", "opponent", "margin")
        }
        action_diff = sum(a != b for a, b in zip(baseline["actions"], candidate["actions"]))
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": baseline["score"],
            "candidate": candidate["score"],
            "delta": delta,
            "action_difference_count": action_diff,
            "suppressed_hires": candidate["telemetry"].get("suppressed_hires", 0),
            "suppressed_costs": candidate["telemetry"].get("suppressed_costs", {}),
            "turns_changed": candidate["telemetry"].get("marginal_hire_turns_changed", 0),
        })

    self_summary = summarize(rows, "self")
    margin_summary = summarize(rows, "margin")
    result = {
        "schema": "kaggriculture.marginal-hire-suppression.v0",
        "candidate": {
            "name": "Marginal HIRE Suppression v0",
            "threshold": candidate_agent.THRESHOLD,
            "operation": "remove final-market HIRE orders with marginal daily Fibonacci cost >= threshold",
            "other_policy_changes": "none",
            "adopted": False,
        },
        "frame": {
            "opponent": OPPONENT,
            "seeds": [5102, 5121],
            "battle_count": len(CASES),
            "seat_balance": {"seat0": 10, "seat1": 10},
        },
        "cases": rows,
        "summary": {
            "self": self_summary,
            "margin": margin_summary,
            "baseline_wins": sum(r["baseline"]["win"] for r in rows),
            "candidate_wins": sum(r["candidate"]["win"] for r in rows),
            "action_difference_cases": sum(r["action_difference_count"] > 0 for r in rows),
            "total_action_differences": sum(r["action_difference_count"] for r in rows),
            "total_suppressed_hires": sum(r["suppressed_hires"] for r in rows),
            "suppressed_hire_cases": sum(r["suppressed_hires"] > 0 for r in rows),
            "large_loss_self_le_minus_5000": sum(r["delta"]["self"] <= -5000 for r in rows),
        },
        "boundary": {
            "status": "battle_evidence_only",
            "promote": False,
            "note": "This run tests one predeclared high-leverage candidate. No separator rescue or threshold sweep is implied by this result.",
        },
    }
    Path("marginal_hire_suppression_v0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print("MARGINAL_HIRE_V0 " + json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
