#!/usr/bin/env python3
"""Matched A/B for Remaining-Time x Recovery-Time Gate v1."""
import json
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import remaining_time_recovery_gate_v1 as gate

OPPONENT = base.OPPONENT
# Fresh and disjoint from the MILK Hold fresh20.
CASES = [(4122 + i, i % 2) for i in range(20)]


def play(agent_fn, seed, seat, reset=None):
    base._configure_baseline()
    if reset:
        reset()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[seat] = agent_fn
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return rewards[seat], rewards[seat] - rewards[1 - seat]


def main():
    rows = []
    for seed, seat in CASES:
        b, bm = play(baseline.agent, seed, seat)
        g, gm = play(gate.agent, seed, seat, gate.reset_experiment)
        rows.append({
            "seed": seed, "seat": seat,
            "gate_count": gate.get_gate_count(),
            "baseline_self": b, "candidate_self": g, "self_diff": g - b,
            "baseline_margin": bm, "candidate_margin": gm, "margin_diff": gm - bm,
        })

    mean = lambda k: sum(r[k] for r in rows) / len(rows)
    summary = {
        "case_count": len(rows),
        "activated_cases": sum(r["gate_count"] > 0 for r in rows),
        "activation_count": sum(r["gate_count"] for r in rows),
        "mean_baseline_self": mean("baseline_self"),
        "mean_candidate_self": mean("candidate_self"),
        "mean_self_diff": mean("self_diff"),
        "mean_margin_diff": mean("margin_diff"),
        "improved": sum(r["self_diff"] > 0 for r in rows),
        "worsened": sum(r["self_diff"] < 0 for r in rows),
        "equal": sum(r["self_diff"] == 0 for r in rows),
    }
    out = {
        "hypothesis": "new late investment should be suppressed when remaining time is shorter than recovery time plus one-cycle slack",
        "relation": "Remaining Time x Recovery Time",
        "test": "fresh20 seeds 4122-4141, alternating seats",
        "change": "within final recovery allowance, remove only market BUY actions; SELL/liquidation untouched",
        "parameters": {
            "total_days": gate.TOTAL_DAYS,
            "expected_recovery_turns": gate.EXPECTED_RECOVERY_TURNS,
            "cycle_slack_turns": gate.CYCLE_SLACK_TURNS,
            "min_required_turns": gate.MIN_REQUIRED_TURNS,
        },
        "causal_attribution": False,
        "cases": rows,
        "summary": summary,
    }
    open("remaining_time_recovery_gate_v1.json", "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    )
    print("REMAINING_TIME_RECOVERY_GATE_V1 " + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    main()
