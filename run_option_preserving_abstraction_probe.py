#!/usr/bin/env python3
"""Paired Abstraction Probe: option-preserving vs no abstraction."""

import json
import os
from pathlib import Path

from kaggle_environments import make
import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
CASES = ((3202, 0), (3206, 0), (3215, 1))


def configure(abstraction):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    if abstraction is None:
        os.environ.pop("G15_STRATEGY_ABSTRACTION", None)
    else:
        os.environ["G15_STRATEGY_ABSTRACTION"] = abstraction
    agent.set_control_enabled(True)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def score(rewards, seat):
    own = float(rewards[seat]); opp = float(rewards[1-seat])
    return {"self": own, "opponent": opp, "margin": own-opp, "win": own > opp}


def snapshots(trace):
    try:
        return trace["body"]["observe"]["body"]["snapshots"]
    except Exception:
        return []


def play(seed, seat, abstraction):
    configure(abstraction)
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        return agent.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [state.reward for state in env.state]
    trace = agent.get_trace()
    snaps = snapshots(trace)
    received = sum(
        1 for s in snaps
        if (s.get("origin_integration") or {}).get("strategy_instruction") == abstraction
    ) if abstraction else 0
    affected = sum(
        1 for s in snaps
        if (s.get("origin_integration") or {}).get("abstraction_effect")
        == "reduce_commitment_preserve_optional_space"
    )
    return {
        "score": score(rewards, seat),
        "abstraction_received_snapshots": received,
        "abstraction_effect_snapshots": affected,
        "snapshot_count": len(snaps),
    }


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, None)
        candidate = play(seed, seat, "option_preserving")
        delta = {
            k: candidate["score"][k] - baseline["score"][k]
            for k in ("self", "opponent", "margin")
        }
        rows.append({
            "seed": seed,
            "seat": seat,
            "baseline_score": baseline["score"],
            "candidate_score": candidate["score"],
            "terminal_delta": delta,
            "direction": "improved" if delta["margin"] > 0 else ("worsened" if delta["margin"] < 0 else "equal"),
            "abstraction": "option_preserving",
            "candidate_response": {
                "received_snapshots": candidate["abstraction_received_snapshots"],
                "effect_snapshots": candidate["abstraction_effect_snapshots"],
                "snapshot_count": candidate["snapshot_count"],
            },
            "causal_attribution": False,
            "promote": False,
        })

    margins = [r["terminal_delta"]["margin"] for r in rows]
    result = {
        "schema": "kaggriculture.abstraction-probe.option-preserving.v0",
        "abstraction": {
            "name": "option_preserving",
            "meaning": "preserve optional space by reducing commitment strength without choosing direction",
            "direct_action_instruction": False,
            "direction_source": "native_origin",
        },
        "cases": rows,
        "summary": {
            "battle_count": len(rows),
            "mean_margin_delta": sum(margins) / len(margins),
            "improved_count": sum(x > 0 for x in margins),
            "worsened_count": sum(x < 0 for x in margins),
            "equal_count": sum(x == 0 for x in margins),
            "total_received_snapshots": sum(r["candidate_response"]["received_snapshots"] for r in rows),
            "total_effect_snapshots": sum(r["candidate_response"]["effect_snapshots"] for r in rows),
        },
        "boundary": "abstraction_probe_paired_battle_no_rule_promotion",
        "causal_attribution": False,
        "promote": False,
    }
    Path("option_preserving_abstraction_probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
