#!/usr/bin/env python3
"""Independent Battle for the frozen Closure conditional candidate.

Frozen candidate:
- abstraction = option_preserving
- gain = 0.60
- current-State gate: units >= 5
- native Origin keeps direction
- no other separator or tuning

Fresh40 5002-5041 is disjoint from known12, fresh20, discovery fresh40,
and the separator audit population.
"""

import copy
import json
import os
from pathlib import Path
from statistics import mean, median

from kaggle_environments import make
import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
CASES = tuple((5002 + i, i % 2) for i in range(40))
GAIN = 0.60
MIN_UNITS = 5
LARGE_LOSS = -5000.0


def configure(candidate=False):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"

    if candidate:
        os.environ["G15_STRATEGY_ABSTRACTION"] = "option_preserving"
        os.environ["G15_OPTION_PRESERVING_GAIN"] = str(GAIN)
        os.environ["G15_OPTION_PRESERVING_MIN_UNITS"] = str(MIN_UNITS)
    else:
        os.environ.pop("G15_STRATEGY_ABSTRACTION", None)
        os.environ.pop("G15_OPTION_PRESERVING_GAIN", None)
        os.environ.pop("G15_OPTION_PRESERVING_MIN_UNITS", None)

    agent.set_control_enabled(True)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def score(rewards, seat):
    own = float(rewards[seat])
    opp = float(rewards[1-seat])
    return {"self": own, "opponent": opp, "margin": own - opp, "win": own > opp}


def snapshots(trace):
    try:
        return trace["body"]["observe"]["body"]["snapshots"]
    except Exception:
        return []


def play(seed, seat, candidate=False):
    configure(candidate)
    actions = []
    current_units = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        me = obs["farms"][obs["player"]]
        current_units.append(1 + len(me.get("hands", [])))
        action = agent.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)

    rewards = [state.reward for state in env.state]
    trace = agent.get_trace()
    snaps = snapshots(trace)

    eligible_turns = sum(u >= MIN_UNITS for u in current_units)
    below_gate_turns = sum(u < MIN_UNITS for u in current_units)
    applied_signal_turns = sum(
        1 for s, u in zip(snaps, current_units)
        if u >= MIN_UNITS
        and (s.get("applied_origin_integration") or {}).get("abstraction_effect")
            == "reduce_commitment_preserve_optional_space"
    )
    gated_off_signal_turns = sum(
        1 for s, u in zip(snaps, current_units)
        if u < MIN_UNITS
        and (s.get("applied_origin_integration") or {}).get("abstraction_effect")
            == "reduce_commitment_preserve_optional_space"
    )

    return {
        "score": score(rewards, seat),
        "actions": actions,
        "snapshot_count": len(snaps),
        "eligible_turns": eligible_turns,
        "below_gate_turns": below_gate_turns,
        "applied_signal_turns": applied_signal_turns,
        "gated_off_signal_turns": gated_off_signal_turns,
    }


def first_difference(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    return min(len(left), len(right)) if len(left) != len(right) else None


def diff_count(left, right):
    return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


def summarize(rows):
    self_d = [r["terminal_delta"]["self"] for r in rows]
    margin_d = [r["terminal_delta"]["margin"] for r in rows]
    return {
        "battle_count": len(rows),
        "self": {
            "improved": sum(x > 0 for x in self_d),
            "worsened": sum(x < 0 for x in self_d),
            "equal": sum(x == 0 for x in self_d),
            "mean_delta": mean(self_d),
            "median_delta": median(self_d),
            "min_delta": min(self_d),
            "max_delta": max(self_d),
            "large_loss_count": sum(x <= LARGE_LOSS for x in self_d),
        },
        "margin": {
            "improved": sum(x > 0 for x in margin_d),
            "worsened": sum(x < 0 for x in margin_d),
            "equal": sum(x == 0 for x in margin_d),
            "mean_delta": mean(margin_d),
            "median_delta": median(margin_d),
            "min_delta": min(margin_d),
            "max_delta": max(margin_d),
        },
        "wins": {
            "baseline": sum(bool(r["baseline_score"]["win"]) for r in rows),
            "candidate": sum(bool(r["candidate_score"]["win"]) for r in rows),
        },
        "runtime": {
            "action_difference_cases": sum(r["action_difference_count"] > 0 for r in rows),
            "total_action_differences": sum(r["action_difference_count"] for r in rows),
            "eligible_turns": sum(r["candidate_runtime"]["eligible_turns"] for r in rows),
            "below_gate_turns": sum(r["candidate_runtime"]["below_gate_turns"] for r in rows),
            "applied_signal_turns": sum(r["candidate_runtime"]["applied_signal_turns"] for r in rows),
            "gated_off_signal_turns": sum(r["candidate_runtime"]["gated_off_signal_turns"] for r in rows),
        },
    }


def main():
    rows = []
    for seed, seat in CASES:
        baseline = play(seed, seat, candidate=False)
        candidate = play(seed, seat, candidate=True)
        delta = {
            k: candidate["score"][k] - baseline["score"][k]
            for k in ("self", "opponent", "margin")
        }
        row = {
            "seed": seed,
            "seat": seat,
            "baseline_score": baseline["score"],
            "candidate_score": candidate["score"],
            "terminal_delta": delta,
            "first_action_difference": first_difference(baseline["actions"], candidate["actions"]),
            "action_difference_count": diff_count(baseline["actions"], candidate["actions"]),
            "candidate_runtime": {
                "eligible_turns": candidate["eligible_turns"],
                "below_gate_turns": candidate["below_gate_turns"],
                "applied_signal_turns": candidate["applied_signal_turns"],
                "gated_off_signal_turns": candidate["gated_off_signal_turns"],
            },
            "causal_attribution": False,
            "promote": False,
        }
        rows.append(row)
        print("CASE " + json.dumps({
            "seed": seed,
            "seat": seat,
            "self_diff": delta["self"],
            "margin_diff": delta["margin"],
            "action_differences": row["action_difference_count"],
            "eligible_turns": candidate["eligible_turns"],
        }, separators=(",", ":")))

    summary = summarize(rows)
    independent_gate_pass = (
        summary["self"]["mean_delta"] > 0
        and summary["self"]["improved"] > summary["self"]["worsened"]
        and summary["self"]["large_loss_count"] == 0
    )

    result = {
        "schema": "kaggriculture.closure-units5-gain060-independent-fresh40.v0",
        "question": "Does the frozen units>=5 conditional option_preserving gain 0.60 reproduce terminal-self improvement without large-loss tail on unseen Battles?",
        "benchmark": {
            "name": "independent-fresh40-5002-5041",
            "cases": [{"seed": s, "seat": seat} for s, seat in CASES],
            "disjoint_from_known12": True,
            "disjoint_from_fresh20_4802_4821": True,
            "disjoint_from_discovery_fresh40_4902_4941": True,
        },
        "candidate": {
            "abstraction": "option_preserving",
            "gain": GAIN,
            "gate": "current_units >= 5",
            "min_units": MIN_UNITS,
            "direction_source": "native_origin",
            "direct_action_instruction": False,
            "other_conditions": None,
        },
        "evaluation_gate": {
            "mean_self_gt_zero": True,
            "improved_gt_worsened": True,
            "large_loss_threshold": LARGE_LOSS,
            "large_loss_count_must_equal": 0,
        },
        "rows": rows,
        "summary": summary,
        "independent_gate_pass": independent_gate_pass,
        "decision": (
            "KEEP_CONDITIONAL_CANDIDATE_FOR_NEXT_ADOPTION_STEP"
            if independent_gate_pass
            else "CLOSE_CLOSURE_RECEIVER"
        ),
        "boundary": {
            "independent_battle": True,
            "separator_frozen_before_run": True,
            "gain_frozen_before_run": True,
            "no_gain_sweep": True,
            "no_new_observer": True,
            "causal_attribution": False,
            "promote": False,
            "adopt": False,
        },
    }

    Path("closure_units5_gain060_independent_fresh40_v0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CLOSURE_UNITS5_GAIN060_INDEPENDENT " + json.dumps({
        "summary": summary,
        "independent_gate_pass": independent_gate_pass,
        "decision": result["decision"],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
