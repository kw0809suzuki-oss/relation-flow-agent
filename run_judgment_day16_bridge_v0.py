#!/usr/bin/env python3
"""Day16 Judgment -> Minimal Intervention -> Battle bridge v0.

One observed State, three arms:
A Current G17
B workload-reduction projection
C work-capacity-increase projection

No abstract claim is adopted from the result.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import g17_agent as current
import judgment_day16_minimal_intervention_v0 as probe

SEED = 6301
SEAT = 0
OPPONENT = "opponents/seyamalam_v21.py"
OUT = Path("judgment_day16_bridge_v0.json")


def configure(module=None, mode=None):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    if module is None:
        current.reset_telemetry()
    else:
        module.set_probe_enabled(True)
        module.set_attribution_enabled(True)
        module.reset_experiment(mode)


def play(fn, module=None, mode=None):
    configure(module, mode)
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    players = [OPPONENT, OPPONENT]
    players[SEAT] = fn
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return {
        "self": rewards[SEAT],
        "opponent": rewards[1-SEAT],
        "margin": rewards[SEAT] - rewards[1-SEAT],
        "win": rewards[SEAT] > rewards[1-SEAT],
        "first_day16_state": module.get_first_state() if module else None,
        "events": module.get_events() if module else [],
    }


def main():
    a = play(current.agent)
    b = play(probe.agent, probe, "B_reduce_workload")
    c = play(probe.agent, probe, "C_increase_capacity")

    result = {
        "schema": "kaggriculture.judgment-day16-bridge.v0",
        "judgment_claim": {
            "state": "Day16 seed6301 observed State",
            "competition": [
                "B: reduce workload",
                "C: increase work capacity",
            ],
            "status": "unresolved_before_battle",
        },
        "arms": {
            "A": "Current G17",
            "B": "Day16 only: suppress new workload-adding purchases",
            "C": "Day16 only: request one HIRE",
        },
        "results": {"A": a, "B": b, "C": c},
        "diffs": {
            "B_minus_A_self": b["self"] - a["self"],
            "C_minus_A_self": c["self"] - a["self"],
            "B_minus_A_margin": b["margin"] - a["margin"],
            "C_minus_A_margin": c["margin"] - a["margin"],
        },
        "interpretation_boundary": [
            "Concrete intervention outcome does not directly prove or reject the abstract Judgment claim.",
            "If an intervention does not fire or is invalid, classify as Action Realization / Reachability before judging Selection.",
            "One seed is a bridge probe, not a robustness result.",
            "No arm is adopted automatically.",
        ],
    }

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_DAY16_BRIDGE_V0 " + json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
