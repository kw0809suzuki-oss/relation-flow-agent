#!/usr/bin/env python3
"""Paired fresh10 Battle for Investment Deadline Coordinate v0."""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import investment_deadline_coordinate_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"investment_deadline_coordinate_v0_{SEED}.json")

def configure_current():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()

def configure_candidate():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    candidate.set_probe_enabled(True)
    candidate.set_attribution_enabled(True)
    candidate.reset_experiment()

def snap(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "hands":len(me.get("hands",[]) or []),
        "land":len(me.get("unlocked_quadrants",[]) or []),
    }

def play(mode):
    if mode=="baseline":
        configure_current()
    else:
        configure_candidate()
    daily={}
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    def agent(obs):
        daily[int(obs.get("day",0) or 0)]=snap(obs)
        return current.agent(obs) if mode=="baseline" else candidate.agent(obs)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    tele=candidate.get_experiment_telemetry() if mode=="candidate" else {}
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "days":{str(d):daily.get(d) for d in (14,18,22,24,29) if d in daily},
        "telemetry":tele,
    }

def main():
    baseline=play("baseline")
    variant=play("candidate")
    b=baseline["terminal"]; v=variant["terminal"]
    tele=variant["telemetry"]
    flow={}
    for d in ("14","18","22","24","29"):
        bs=baseline["days"].get(d); vs=variant["days"].get(d)
        flow[d]=None if not bs or not vs else {
            "money_diff":vs["money"]-bs["money"],
            "hands_diff":vs["hands"]-bs["hands"],
            "land_diff":vs["land"]-bs["land"],
        }
    payload={
        "schema":"kaggriculture.investment-deadline-coordinate.v0",
        "seed":SEED,"seat":SEAT,
        "baseline":baseline,
        "candidate":variant,
        "reachability":{
            "considered":tele.get("considered",0),
            "allowed_after_d14":tele.get("allowed_after_d14",0),
            "removed_by_deadline":tele.get("removed_by_deadline",0),
            "removed_land_d14":tele.get("removed_land_d14",0),
            "reached":tele.get("allowed_after_d14",0)>0 or tele.get("removed_by_deadline",0)>0,
            "event_days":sorted({e["day"] for e in tele.get("events",[]) if e.get("day") is not None}),
        },
        "flow_change":flow,
        "terminal_effect":{
            "self_diff":v["self"]-b["self"],
            "margin_diff":v["margin"]-b["margin"],
            "baseline_win":b["win"],
            "candidate_win":v["win"],
            "direction":"improved" if v["self"]>b["self"] else "worsened" if v["self"]<b["self"] else "equal",
        },
        "boundary":[
            "Baseline is Current Combat Model with fixed D14 closure and HIRE preserved.",
            "Candidate changes only post-D14 SEED/COW investment closure to recovery-deadline logic.",
            "LAND remains fixed D14 closure because its recovery horizon is unresolved.",
            "SEED uses FIRST_YIELD[crop]+1; COW uses the existing 8-day recovery test horizon.",
            "HIRE/HARVEST/SELL/unit actions are unchanged.",
            "Fresh paired seed/seat comparison; no auto-adoption."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("INVESTMENT_DEADLINE_COORDINATE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
