#!/usr/bin/env python3
"""Paired fresh10 Battle for Liquidation Deadline Coordinate v0."""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import liquidation_deadline_coordinate_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"liquidation_deadline_coordinate_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()

def snap(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    private=obs.get("private",{}) or {}
    shed=private.get("shed",{}) or {}
    inventories=private.get("inventories",[]) or []
    carried=sum(
        sum(int(inv.get(k,0) or 0) for k in ("WHEAT","STRAWBERRY","MELON"))
        for inv in inventories if isinstance(inv,dict)
    )
    shed_crop=sum(int(shed.get(k,0) or 0) for k in ("WHEAT","STRAWBERRY","MELON"))
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "carried_crop":carried,
        "shed_crop":shed_crop,
    }

def play(mode):
    configure()
    if mode=="candidate":
        candidate.reset_experiment()
    last={}
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        last.clear(); last.update(snap(obs))
        return candidate.agent(obs) if mode=="candidate" else current.agent(obs)

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
        "last_observation":dict(last),
        "telemetry":tele,
    }

def main():
    baseline=play("baseline")
    variant=play("candidate")
    b=baseline["terminal"]; v=variant["terminal"]
    tele=variant["telemetry"]
    bl=baseline["last_observation"]; vl=variant["last_observation"]
    payload={
        "schema":"kaggriculture.liquidation-deadline-coordinate.v0",
        "seed":SEED,
        "seat":SEAT,
        "baseline":baseline,
        "candidate":variant,
        "reachability":{
            "eligible":tele.get("eligible",0),
            "deadline_hits":tele.get("deadline_hits",0),
            "move_overrides":tele.get("move_overrides",0),
            "drop_overrides":tele.get("drop_overrides",0),
            "reached":tele.get("deadline_hits",0)>0,
            "event_days":sorted({e["day"] for e in tele.get("events",[])}),
            "event_remaining_turns":sorted({e["remaining_turns"] for e in tele.get("events",[])}),
        },
        "flow_change":{
            "last_money_diff":vl.get("money",0)-bl.get("money",0),
            "last_carried_crop_diff":vl.get("carried_crop",0)-bl.get("carried_crop",0),
            "last_shed_crop_diff":vl.get("shed_crop",0)-bl.get("shed_crop",0),
        },
        "terminal_effect":{
            "self_diff":v["self"]-b["self"],
            "margin_diff":v["margin"]-b["margin"],
            "baseline_win":b["win"],
            "candidate_win":v["win"],
            "direction":"improved" if v["self"]>b["self"] else "worsened" if v["self"]<b["self"] else "equal",
        },
        "boundary":[
            "Strategic coordinate only: protect terminal conversion of already-carried crop value.",
            "Experimental clock assumes 24 agent calls/day and 30 days, consistent with observed traces but not promoted as a game-rule claim here.",
            "Required turns = shortest shed distance + DROP + next-turn SELL.",
            "No HARVEST, BUY, HIRE, SELL, price, or reserve rule is changed.",
            "Fresh paired seed/seat comparison; no auto-adoption."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LIQUIDATION_DEADLINE_COORDINATE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
