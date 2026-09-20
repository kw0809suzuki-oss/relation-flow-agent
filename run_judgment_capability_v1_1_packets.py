#!/usr/bin/env python3
"""Verify v1.1 Triage/Boundary packet on real unchanged G17 State.

This is a structural verification run only.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as current
from judgment_capability_v1_1 import build_packet, guide

OPPONENT = base.OPPONENT
CASES = [(6201, 0), (6202, 1)]
OUT = Path("judgment_capability_v1_1_packets.json")


def configure():
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
    current.reset_telemetry()


def play(seed, seat):
    configure()
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    packets = []
    last_day = None

    def observed(obs):
        nonlocal last_day
        day = int(obs.get("day", 0) or 0)
        packet = build_packet(obs)
        if day != last_day:
            packets.append(packet)
            last_day = day
        else:
            packets[-1] = packet
        return current.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[seat] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return {
        "seed": seed,
        "seat": seat,
        "terminal": {
            "self": rewards[seat],
            "opponent": rewards[1-seat],
            "margin": rewards[seat] - rewards[1-seat],
        },
        "packets": packets,
    }


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    payload = {
        "schema": "kaggriculture.judgment-capability-v1.1-packets",
        "policy_mutated": False,
        "guide": guide(),
        "cases": cases,
        "boundary": [
            "Triage labels are not decision weights.",
            "Hint truth is not decided.",
            "Hint relevance is not precomputed.",
            "No direction is generated.",
            "No action is generated.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_CAPABILITY_V11_SUMMARY " + json.dumps({
        "cases": len(cases),
        "packet_counts": [len(c["packets"]) for c in cases],
        "triage": {
            h["name"]: h["triage"]
            for h in JUDGMENT_GUIDE_V11["relation_hints"]
        },
        "hint_truth_decided_any": any(
            p["boundary"]["hint_truth_decided"] for c in cases for p in c["packets"]
        ),
        "triage_used_as_weight_any": any(
            p["boundary"]["triage_used_as_weight"] for c in cases for p in c["packets"]
        ),
        "hint_relevance_precomputed_any": any(
            p["boundary"]["hint_relevance_precomputed"] for c in cases for p in c["packets"]
        ),
        "direction_precomputed_any": any(
            p["boundary"]["direction_precomputed"] for c in cases for p in c["packets"]
        ),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
