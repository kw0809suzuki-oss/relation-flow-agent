#!/usr/bin/env python3
"""Observe Judgment Capability v0 on unchanged Current G17 play.

No actions are changed. One packet per game day is retained so we can inspect
how the open Direction Space changes as the farm evolves.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as current
from judgment_capability_v0 import judgment_packet, guide

OPPONENT = base.OPPONENT
CASES = [(6001, 0), (6002, 1), (6003, 0)]
OUT = Path("judgment_capability_observe_v0.json")


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
        packet = judgment_packet(obs)
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
        "daily_judgment_packets": packets,
    }


def compact(case):
    out = []
    for packet in case["daily_judgment_packets"]:
        state = packet["state"]
        ds = packet["direction_space"]
        out.append({
            "day": state["day"],
            "remaining": state["remaining_horizon"],
            "money": state["money"],
            "grow_support_n": len(ds["grow"]["support"]),
            "earn_support_n": len(ds["earn"]["support"]),
            "recover_support_n": len(ds["recover"]["support"]),
            "grow_support": ds["grow"]["support"],
            "earn_support": ds["earn"]["support"],
            "recover_support": ds["recover"]["support"],
        })
    return out


def main():
    cases = [play(seed, seat) for seed, seat in CASES]
    payload = {
        "schema": "kaggriculture.judgment-capability-observe.v0",
        "policy_mutated": False,
        "guide": guide(),
        "cases": cases,
        "boundary": [
            "Current G17 actions are unchanged.",
            "No direction is selected.",
            "No action is generated.",
            "Support signals are observation scaffolds, not proven causal rules.",
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_CAPABILITY_V0_SUMMARY " + json.dumps({
        "cases": len(cases),
        "terminals": [c["terminal"] for c in cases],
        "daily_packet_counts": [len(c["daily_judgment_packets"]) for c in cases],
    }, separators=(",", ":")))
    for c in cases:
        print("JUDGMENT_CAPABILITY_V0_CASE " + json.dumps({
            "seed": c["seed"],
            "terminal": c["terminal"],
            "days": compact(c),
        }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
