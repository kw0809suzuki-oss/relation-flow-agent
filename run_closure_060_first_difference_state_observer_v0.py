#!/usr/bin/env python3
"""One-shot observation after Closure gain 0.60 fresh40.

Question:
At the first baseline-vs-candidate Action difference, do the strongest
fresh40 improvements and strongest fresh40 accidents occupy visibly different
existing State / receiver contexts?

This is observer-only. It does not alter the candidate or promote a rule.
"""

import copy
import json
import os
from pathlib import Path

from kaggle_environments import make
import whole_flow_control_agent_v2 as agent


OPPONENT = "opponents/seyamalam_v21.py"
GAIN = 0.60

# Fixed from the completed fresh40 terminal result. No relabeling during this run.
IMPROVED4 = ((4933, 1), (4916, 0), (4917, 1), (4934, 0))
ACCIDENT4 = ((4938, 0), (4940, 0), (4910, 0), (4918, 0))
CASES = tuple(("improved4", s, seat) for s, seat in IMPROVED4) + tuple(
    ("accident4", s, seat) for s, seat in ACCIDENT4
)


def configure(abstraction=None, gain=None):
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
        os.environ.pop("G15_OPTION_PRESERVING_GAIN", None)
    else:
        os.environ["G15_STRATEGY_ABSTRACTION"] = abstraction
        os.environ["G15_OPTION_PRESERVING_GAIN"] = str(gain)

    agent.set_control_enabled(True)
    agent.set_probe_enabled(True)
    agent.set_attribution_enabled(True)
    agent.reset_telemetry()


def econ_state(obs):
    player = int(obs["player"])
    me = obs["farms"][player]
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []

    def total(item):
        return shed.get(item, 0) + sum((inv or {}).get(item, 0) for inv in inventories)

    cows = total("COW")
    for row in me.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                cows += 1

    outputs = sum(total(k) for k in ("MILK", "WOOL", "EGG", "FERTILIZER"))
    market = obs.get("market", {}) or {}
    prices = market.get("prices", {}) or {}

    return {
        "day": obs.get("day"),
        "hour": obs.get("hour"),
        "money": me.get("money", 0),
        "units": 1 + len(me.get("hands", [])),
        "land": len(me.get("unlocked_quadrants", [])),
        "cows": cows,
        "wheat": total("WHEAT"),
        "outputs": outputs,
        "milk_price": prices.get("MILK"),
        "wheat_price": prices.get("WHEAT"),
    }


def play(seed, seat, abstraction=None, gain=None):
    configure(abstraction, gain)
    actions = []
    states = []
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)

    def observed(obs):
        states.append(econ_state(obs))
        action = agent.agent(obs)
        actions.append(copy.deepcopy(action))
        return action

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [float(state.reward) for state in env.state]
    return {
        "self": rewards[seat],
        "opponent": rewards[1-seat],
        "margin": rewards[seat] - rewards[1-seat],
        "actions": actions,
        "states": states,
        "trace": agent.get_trace(),
    }


def first_difference(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return i
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def candidate_snapshot_at(trace, index):
    try:
        snaps = trace["body"]["observe"]["body"]["snapshots"]
        if 0 <= index < len(snaps):
            s = snaps[index]
            integ = dict(s.get("origin_integration") or {})
            return {
                "mode": s.get("mode"),
                "R": s.get("R"),
                "E": s.get("E"),
                "W": s.get("W"),
                "resonance": s.get("resonance"),
                "target": s.get("target"),
                "feed_carry": s.get("feed_carry"),
                "native_strength": integ.get("native_strength"),
                "context_reliability": integ.get("context_reliability"),
                "field_evidence": integ.get("field_evidence"),
                "field_alignment": integ.get("field_alignment"),
                "commitment": integ.get("commitment"),
                "abstraction_gain": integ.get("abstraction_gain"),
                "field_phase": integ.get("field_phase"),
            }
    except Exception:
        pass
    return {}


def main():
    rows = []
    for group, seed, seat in CASES:
        baseline = play(seed, seat)
        candidate = play(seed, seat, "option_preserving", GAIN)
        idx = first_difference(baseline["actions"], candidate["actions"])
        row = {
            "group": group,
            "seed": seed,
            "seat": seat,
            "self_diff": candidate["self"] - baseline["self"],
            "margin_diff": candidate["margin"] - baseline["margin"],
            "first_action_difference": idx,
            "baseline_state_at_first_difference": (
                baseline["states"][idx] if idx is not None and idx < len(baseline["states"]) else None
            ),
            "candidate_state_at_first_difference": (
                candidate["states"][idx] if idx is not None and idx < len(candidate["states"]) else None
            ),
            "candidate_receiver_at_first_difference": (
                candidate_snapshot_at(candidate["trace"], idx) if idx is not None else {}
            ),
            "observer_only": True,
            "causal_claim": False,
            "promote": False,
        }
        rows.append(row)
        print("FIRST_DIFF " + json.dumps(row, separators=(",", ":")))

    result = {
        "schema": "kaggriculture.closure-060-first-difference-state-observer.v0",
        "question": "Do strongest improvements and strongest accidents show a coarse existing-State difference at first Action divergence?",
        "source_run": 35566515651,
        "groups": {
            "improved4": [{"seed": s, "seat": seat} for s, seat in IMPROVED4],
            "accident4": [{"seed": s, "seat": seat} for s, seat in ACCIDENT4],
        },
        "rows": rows,
        "boundary": {
            "one_observation_only": True,
            "no_new_intervention": True,
            "causal_claim": False,
            "promote": False,
            "adopt": False,
        },
    }
    Path("closure_060_first_difference_state_observer_v0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
