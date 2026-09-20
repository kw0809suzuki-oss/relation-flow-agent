#!/usr/bin/env python3
"""Judgment packet export v0.

Collect real v1.1 grounded packets for external/manual Judgment reading.
No paid model/API call is made here.
"""
import json
import os
from pathlib import Path

from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as current
from judgment_capability_v1_1 import build_packet

OPPONENT = base.OPPONENT
SEED = 6301
SEAT = 0
SELECT_DAYS = {8, 16, 24}
OUT = Path("judgment_model_probe_v0.json")


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


def collect_packets():
    configure()
    env = make("kaggriculture", configuration={"seed": SEED}, debug=False)
    packets = {}
    last_day = None

    def observed(obs):
        nonlocal last_day
        day = int(obs.get("day", 0) or 0)
        if day in SELECT_DAYS and day != last_day:
            packets[str(day)] = build_packet(
                obs,
                human_direction="目的はterminal selfを伸ばし、最終的には勝率を上げる。方向は仮説として扱う。",
            )
        last_day = day
        return current.agent(obs)

    players = [OPPONENT, OPPONENT]
    players[SEAT] = observed
    env.run(players)
    rewards = [float(s.reward) for s in env.state]
    return packets, {
        "self": rewards[SEAT],
        "opponent": rewards[1-SEAT],
        "margin": rewards[SEAT] - rewards[1-SEAT],
    }


def main():
    packets, terminal = collect_packets()
    payload = {
        "schema": "kaggriculture.judgment-packet-export.v0",
        "status": "ready_for_external_judgment",
        "policy_mutated": False,
        "seed": SEED,
        "seat": SEAT,
        "terminal": terminal,
        "packets": packets,
        "judgment_task": {
            "read_each_hint_against_state": True,
            "allowed_relevance": [
                "relevant",
                "weakly_relevant",
                "not_relevant",
                "conflicting",
                "missing_evidence",
            ],
            "directions_to_consider": ["grow", "earn", "recover"],
            "keep_conflict_and_missing_evidence": True,
            "do_not_generate_action_yet": True,
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JUDGMENT_PACKET_EXPORT_V0 " + json.dumps({
        "status": payload["status"],
        "seed": SEED,
        "terminal": terminal,
        "packet_days": sorted(packets),
        "paid_api_call": False,
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
