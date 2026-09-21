#!/usr/bin/env python3
"""Strength Benchmark v0 worker.

One fixed benchmark seed per job.
Runs the current Combat Model once and records absolute terminal strength metrics.

Environment:
  BATTLE_SEED
  BATTLE_SEAT
  GITHUB_RUN_ID / GITHUB_SHA are recorded when available.
"""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
BENCHMARK="strength_benchmark_v0"
OUT=Path(f"strength_benchmark_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play():
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)

    rewards=[float(x.reward) for x in env.state]
    terminal_self=rewards[SEAT]
    terminal_opponent=rewards[1-SEAT]
    terminal_margin=terminal_self-terminal_opponent
    outcome="win" if terminal_margin>0 else "loss" if terminal_margin<0 else "draw"
    return {
        "terminal_self":terminal_self,
        "terminal_opponent":terminal_opponent,
        "terminal_margin":terminal_margin,
        "outcome":outcome,
    }

def main():
    result=play()
    payload={
        "schema":"kaggriculture.strength-benchmark.v0",
        "benchmark":BENCHMARK,
        "snapshot":"SB-01",
        "run_id":os.environ.get("GITHUB_RUN_ID"),
        "commit":os.environ.get("GITHUB_SHA"),
        "seed":SEED,
        "seat":SEAT,
        **result,
        "artifact":f"strength-benchmark-v0-{SEED}",
        "boundary":[
            "Strength Benchmark measures absolute Current Combat Model strength, not Candidate A/B difference.",
            "Benchmark v0 uses a fixed opponent, seed set, seat pattern, game configuration, scoring path, and aggregation method.",
            "Seeds 7001-7050 are reserved as the fixed Strength Benchmark v0 set.",
            "Current Combat Model includes the formally adopted D14 late-expansion closure rule.",
            "No benchmark-only Candidate or Variant intervention is applied.",
            "Future snapshots must reuse this same Benchmark v0 set unless a new benchmark version is explicitly created."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STRENGTH_BENCHMARK_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
