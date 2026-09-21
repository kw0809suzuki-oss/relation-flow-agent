#!/usr/bin/env python3
"""Independent fresh40 validation for frozen D14 late-expansion suppression."""
import copy
import json
import os
from pathlib import Path
from statistics import median

from kaggle_environments import make

import export_scale_baseline_v1 as scale
import g17_agent as baseline_agent
import d14_late_expansion_closure_v0 as candidate_agent

OPPONENT = scale.OPPONENT
SEEDS = list(range(7301, 7341))
CASES = [(seed, (seed - 7301) % 2) for seed in SEEDS]
OUT = Path("d14_late_expansion_independent_fresh40.json")

def configure_common():
    scale._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"

def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1-seat])
    return {
        "self": own,
        "opponent": opp,
        "margin": own - opp,
        "win": own > opp,
    }

def play(seed, seat, candidate):
    configure_common()
    if hasattr(baseline_agent, "set_probe_enabled"):
        baseline_agent.set_probe_enabled(True)
    if hasattr(baseline_agent, "set_attribution_enabled"):
        baseline_agent.set_attribution_enabled(True)

    if candidate:
        candidate_agent.reset_telemetry()
        body = candidate_agent.agent
    else:
        if hasattr(baseline_agent, "reset_telemetry"):
            baseline_agent.reset_telemetry()
        body = baseline_agent.agent

    actions = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        action = body(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]

    return {
        "score": score(rewards, seat),
        "actions": actions,
        "candidate_telemetry": candidate_agent.get_telemetry() if candidate else None,
    }

def action_diff_count(a, b):
    n = min(len(a), len(b))
    diff = sum(a[i] != b[i] for i in range(n))
    diff += abs(len(a)-len(b))
    return diff

def summarize(values):
    return {
        "mean": sum(values)/len(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
    }

def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, False)
        candidate = play(seed, seat, True)
        ds = candidate["score"]["self"] - baseline["score"]["self"]
        dm = candidate["score"]["margin"] - baseline["score"]["margin"]
        adc = action_diff_count(baseline["actions"], candidate["actions"])
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline": baseline["score"],
            "candidate": candidate["score"],
            "diff_self": ds,
            "diff_margin": dm,
            "self_direction": "improved" if ds > 0 else "worsened" if ds < 0 else "equal",
            "margin_direction": "improved" if dm > 0 else "worsened" if dm < 0 else "equal",
            "action_difference_count": adc,
            "telemetry": candidate["candidate_telemetry"],
        })

    self_d = [r["diff_self"] for r in rows]
    margin_d = [r["diff_margin"] for r in rows]
    summary = {
        "case_count": len(rows),
        "seat0": sum(r["seat"] == 0 for r in rows),
        "seat1": sum(r["seat"] == 1 for r in rows),
        "self": {
            "improved": sum(x > 0 for x in self_d),
            "worsened": sum(x < 0 for x in self_d),
            "equal": sum(x == 0 for x in self_d),
            **summarize(self_d),
            "large_loss_le_-5000": sum(x <= -5000 for x in self_d),
            "loss_le_-2000": sum(x <= -2000 for x in self_d),
        },
        "margin": {
            "improved": sum(x > 0 for x in margin_d),
            "worsened": sum(x < 0 for x in margin_d),
            "equal": sum(x == 0 for x in margin_d),
            **summarize(margin_d),
        },
        "baseline_wins": sum(r["baseline"]["win"] for r in rows),
        "candidate_wins": sum(r["candidate"]["win"] for r in rows),
        "action_difference_cases": sum(r["action_difference_count"] > 0 for r in rows),
        "total_action_differences": sum(r["action_difference_count"] for r in rows),
        "activation_cases": sum((r["telemetry"] or {}).get("changed_calls", 0) > 0 for r in rows),
        "total_changed_calls": sum((r["telemetry"] or {}).get("changed_calls", 0) for r in rows),
        "total_removed_orders": sum((r["telemetry"] or {}).get("removed_orders", 0) for r in rows),
    }

    result = {
        "schema": "kaggriculture.d14-late-expansion-closure.independent-fresh40.v0",
        "candidate": {
            "start_day": 14,
            "suppressed_market_orders": ["BUY_LAND", "BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT COW"],
            "other_conditions": [],
            "frozen": True,
            "adopted": False,
        },
        "comparison": {
            "baseline": "current G17",
            "opponent": OPPONENT,
            "seeds": [7301, 7340],
            "cases": 40,
        },
        "rows": rows,
        "summary": summary,
        "boundary": [
            "Independent seed band not used by the prior D12/D14 fresh50 screen.",
            "Candidate definition is frozen before this run.",
            "No threshold sweep, separator rescue, or result-dependent modification in this run.",
            "Battle evidence only; adoption requires an explicit later decision.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("D14_LATE_EXPANSION_INDEPENDENT_FRESH40 " + json.dumps(summary, ensure_ascii=False, separators=(",",":")))

if __name__ == "__main__":
    main()
