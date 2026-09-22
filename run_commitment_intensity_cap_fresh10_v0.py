#!/usr/bin/env python3
"""Paired fresh10: Completion-only vs Completion + Commitment Intensity Cap v0."""

import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import investment_completion_coordinate_v0 as completion
import commitment_intensity_cap_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"commitment_intensity_cap_v0_{SEED}.json")

def configure_completion():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    completion.set_probe_enabled(True)
    completion.set_attribution_enabled(True)
    completion.reset_experiment()

def configure_candidate():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    candidate.set_probe_enabled(True)
    candidate.set_attribution_enabled(True)
    candidate.reset_experiment()

def play(mode):
    configure_completion() if mode=="completion" else configure_candidate()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=completion.agent if mode=="completion" else candidate.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    tele=completion.get_experiment_telemetry() if mode=="completion" else candidate.get_experiment_telemetry()
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "telemetry":tele,
    }

def main():
    b=play("completion")
    v=play("candidate")
    bt=b["terminal"]; vt=v["terminal"]
    tele=v["telemetry"]
    events=list(tele.get("events",[]) or [])
    payload={
        "schema":"kaggriculture.commitment-intensity-cap.v0",
        "seed":SEED,"seat":SEAT,
        "control_completion":b,
        "candidate":v,
        "reachability":{
            "seed_orders_after_completion":tele.get("seed_orders_after_completion",0),
            "removed_by_intensity":tele.get("seed_orders_removed_intensity",0),
            "allowed_by_intensity":tele.get("seed_orders_allowed_intensity",0),
            "reached":tele.get("seed_orders_removed_intensity",0)>0,
            "remove_days":sorted({e.get("day") for e in events if e.get("kind")=="remove"}),
            "max_observed_intensity":max([e.get("commitment_intensity") for e in events if e.get("commitment_intensity") is not None] or [0]),
        },
        "terminal_effect":{
            "self_diff":vt["self"]-bt["self"],
            "margin_diff":vt["margin"]-bt["margin"],
            "control_win":bt["win"],
            "candidate_win":vt["win"],
            "direction":"improved" if vt["self"]>bt["self"] else "worsened" if vt["self"]<bt["self"] else "equal",
        },
        "boundary":[
            "Control is Investment Completion Coordinate v0.",
            "Candidate adds only a 2.5% single-SEED commitment-intensity cap after completion filtering.",
            "Intensity is seed order cost divided by current pre-action cash for that turn.",
            "2.5% is an experimental boundary, not an adopted rule.",
            "No rescue conditions and no changes to LAND/COW/HIRE/HARVEST/SELL/unit actions beyond the completion control."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COMMITMENT_INTENSITY_CAP_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
