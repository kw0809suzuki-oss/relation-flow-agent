#!/usr/bin/env python3
"""Paired fresh10 Battle for Expansion Cycle Candidate v0.

Current Combat Model vs one observation-derived intervention:
convert already-owned day-7 expansion capacity into workforce + one NE MELON lane.

Evaluation layers:
Reachability -> intervention actually fires and NE MELON appears.
Flow Change -> hands / NE MELON / money trajectory changes.
Terminal -> self / margin / win.
"""
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as current
import expansion_cycle_candidate_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"expansion_cycle_candidate_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    current.set_control_enabled(False)
    current.set_probe_enabled(True)
    current.set_attribution_enabled(True)
    current.reset_telemetry()

def snapshot(obs):
    p=int(obs["player"])
    me=obs["farms"][p]
    tiles=me.get("tiles",[]) or []
    h=len(tiles)//2 if tiles else 0
    total_melon=0
    ne_melon=0
    for y,row in enumerate(tiles):
        for x,tile in enumerate(row or []):
            if isinstance(tile,dict) and tile.get("kind")=="PLANT" and tile.get("crop")=="MELON":
                total_melon+=1
                if y<h and x>=h:
                    ne_melon+=1
    private=obs.get("private",{}) or {}
    stores=[private.get("shed",{}) or {}]+list(private.get("inventories",[]) or [])
    melon_stock=sum(int(s.get("MELON",0) or 0) for s in stores if isinstance(s,dict))
    return {
        "day":int(obs.get("day",0) or 0),
        "money":float(me.get("money",0) or 0),
        "hands":len(me.get("hands",[]) or []),
        "land":len(me.get("unlocked_quadrants",[]) or []),
        "melon_plants":total_melon,
        "ne_melon_plants":ne_melon,
        "melon_stock":melon_stock,
    }

def play(mode):
    configure()
    if mode=="candidate":
        candidate.reset_experiment()

    daily={}
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        daily[int(obs.get("day",0) or 0)]=snapshot(obs)
        return candidate.agent(obs) if mode=="candidate" else current.agent(obs)

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    telemetry=candidate.get_experiment_telemetry() if mode=="candidate" else {}
    selected_days={str(d):daily.get(d) for d in (6,7,8,10,17,18,24,29) if d in daily}
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "days":selected_days,
        "telemetry":telemetry,
    }

def main():
    baseline=play("baseline")
    variant=play("candidate")
    b=baseline["terminal"]; v=variant["terminal"]

    tele=variant["telemetry"]
    reachability={
        "eligible_calls":tele.get("eligible_calls",0),
        "hire_orders_added":tele.get("hire_orders_added",0),
        "seed_orders_added":tele.get("seed_orders_added",0),
        "steer_overrides":tele.get("steer_overrides",0),
        "plant_overrides":tele.get("plant_overrides",0),
        "reached_local_behavior":bool(
            tele.get("hire_orders_added",0)
            or tele.get("seed_orders_added",0)
            or tele.get("steer_overrides",0)
            or tele.get("plant_overrides",0)
        ),
    }

    b8=(baseline["days"].get("8") or {})
    v8=(variant["days"].get("8") or {})
    b17=(baseline["days"].get("17") or {})
    v17=(variant["days"].get("17") or {})
    flow={
        "day8_hands_diff":(v8.get("hands",0)-b8.get("hands",0)) if b8 and v8 else None,
        "day8_ne_melon_diff":(v8.get("ne_melon_plants",0)-b8.get("ne_melon_plants",0)) if b8 and v8 else None,
        "day8_money_diff":(v8.get("money",0)-b8.get("money",0)) if b8 and v8 else None,
        "day17_money_diff":(v17.get("money",0)-b17.get("money",0)) if b17 and v17 else None,
        "day17_melon_stock_diff":(v17.get("melon_stock",0)-b17.get("melon_stock",0)) if b17 and v17 else None,
    }

    payload={
        "schema":"kaggriculture.expansion-cycle-candidate.v0",
        "seed":SEED,
        "seat":SEAT,
        "opponent":"Seyamalam v21",
        "baseline":baseline,
        "candidate":variant,
        "reachability":reachability,
        "flow_change":flow,
        "terminal_effect":{
            "self_diff":v["self"]-b["self"],
            "margin_diff":v["margin"]-b["margin"],
            "baseline_win":b["win"],
            "candidate_win":v["win"],
            "direction":"improved" if v["self"]>b["self"] else "worsened" if v["self"]<b["self"] else "equal",
        },
        "boundary":[
            "Fresh paired seed/seat comparison against the current Combat Model.",
            "Candidate does not force BUY_LAND; it acts only when at least two quadrants already exist on day 7.",
            "Candidate targets hands=8, one MELON seed, and one NE MELON planting path.",
            "Short-term cash drawdown is allowed up to actual affordability; no post-result rescue condition exists.",
            "Observed opponent Expansion Cycle motivated the intervention but is not treated as causal proof.",
            "No auto-adoption."
        ],
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("EXPANSION_CYCLE_CANDIDATE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
