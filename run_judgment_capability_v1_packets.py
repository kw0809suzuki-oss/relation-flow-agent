#!/usr/bin/env python3
"""Observe v1 grounded judgment packets on unchanged Current G17 play.

The run verifies only that the packet can be built from real game state without
precomputing a direction. It does not claim the execution AI has judged yet.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as current
from judgment_capability_v1 import build_packet, guide

OPPONENT = base.OPPONENT
CASES = [(6101, 0), (6102, 1), (6103, 0)]
OUT = Path("judgment_capability_v1_packets.json")


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
            "win": rewards[seat] > rewards[1-seat],
        },
        "packets": packets,
    }


def compact(case):
    selected_days = {0, 8, 15, 16, 22, 29}
    rows = []
    for p in case["packets"]:
        day = p["observed_state"]["time"]["day"]
        if day not in selected_days:
            continue
        rows.append({
            "day": day,
            "observed_state": p["observed_state"],
            "relation_hint_names": [x["name"] for x in p["relation_hints"]],
            "direction_precomputed": p["boundary"]["direction_precomputed"],
            "action_precomputed": p["boundary"]["action_precomputed"],
        })
    return rows


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    payload = {
        "schema": "kaggriculture.judgment-capability-v1-packets",
        "policy_mutated": False,
        "guide": guide(),
        "cases": cases,
        "boundary": [
            "Current G17 actions are unchanged.",
            "No direction threshold is encoded.",
            "No direction is selected.",
            "No action is generated.",
            "v1 prepares grounded input for a later execution-AI judgment step.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("JUDGMENT_CAPABILITY_V1_SUMMARY " + json.dumps({
        "cases": len(cases),
        "packet_counts": [len(c["packets"]) for c in cases],
        "terminals": [c["terminal"] for c in cases],
        "direction_precomputed_any": any(
            p["boundary"]["direction_precomputed"]
            for c in cases for p in c["packets"]
        ),
    }, separators=(",", ":")))

    for c in cases:
        print("JUDGMENT_CAPABILITY_V1_CASE " + json.dumps({
            "seed": c["seed"],
            "terminal": c["terminal"],
            "selected_days": compact(c),
        }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
