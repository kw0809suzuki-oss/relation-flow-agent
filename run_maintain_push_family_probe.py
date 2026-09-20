#!/usr/bin/env python3
"""Paired Battle probe for Candidate Family 001: Combat switch vs Economic stop."""

import copy
import json
import os
from pathlib import Path

from kaggle_environments import make

import whole_flow_control_agent_v2 as combat
import whole_flow_control_agent_v2_maintain_push_probe as probe


OPPONENT = "opponents/seyamalam_v21.py"
CASES = ((3202, 0), (3206, 0), (3215, 1))


def configure(agent_module):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    agent_module.set_control_enabled(True)
    agent_module.set_probe_enabled(True)
    agent_module.set_attribution_enabled(True)
    agent_module.reset_telemetry()


def score(rewards, seat):
    own = float(rewards[seat])
    opponent = float(rewards[1 - seat])
    return {"self": own, "opponent": opponent, "margin": own - opponent, "win": own > opponent}


def play(seed, seat, agent_module):
    configure(agent_module)
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        return agent_module.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    return {
        "score": score(rewards, seat),
        "telemetry": agent_module.get_telemetry(),
        "trace": agent_module.get_trace()["whole_flow"],
    }


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, combat)
        candidate = play(seed, seat, probe)
        delta = {
            k: candidate["score"][k] - baseline["score"][k]
            for k in ("self", "opponent", "margin")
        }
        interventions = candidate["telemetry"].get("family_intervention_count", 0)
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline_score": baseline["score"],
            "candidate_score": candidate["score"],
            "terminal_delta": delta,
            "direction": "improved" if delta["margin"] > 0 else ("worsened" if delta["margin"] < 0 else "equal"),
            "family": "maintain->push",
            "intervention_count": interventions,
            "candidate_trace_intervention_count": sum(bool(e.get("family_intervention")) for e in candidate["trace"]),
            "causal_attribution": False,
            "promote": False,
        })

    margins = [r["terminal_delta"]["margin"] for r in rows]
    result = {
        "schema": "kaggriculture.candidate-family-probe.maintain-push.v0",
        "family": {
            "combat": "maintain",
            "economic": "push",
            "source": "repeated_dual_lens_disagreement",
        },
        "cases": rows,
        "summary": {
            "battle_count": len(rows),
            "mean_margin_delta": sum(margins) / len(margins),
            "improved_count": sum(x > 0 for x in margins),
            "worsened_count": sum(x < 0 for x in margins),
            "equal_count": sum(x == 0 for x in margins),
            "total_interventions": sum(r["intervention_count"] for r in rows),
        },
        "boundary": "paired_battle_observation_no_rule_promotion",
        "causal_attribution": False,
        "promote": False,
    }
    Path("maintain_push_family_probe_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
