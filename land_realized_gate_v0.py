#!/usr/bin/env python3
"""LAND Realized Gate observer v0.

Question:
When LAND_policy_open becomes true, does an actual BUY_LAND transformation occur?

Scope:
- existing LAND recovery / seed3 13 cases
- no policy mutation
- no terminal interpretation
- fill only Candidate Bundle: Realized
"""

import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent
import strong_origin

LAND={(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0)}
SEED={(4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)}
CASES=sorted(LAND|SEED)
OPP=base.OPPONENT
START,END=96,140


def latest_snapshot():
    return agent.get_trace()["body"]["observe"]["body"]["snapshots"][-1]


def classify(obs,snap):
    p=int(obs["player"]); me=obs["farms"][p]
    day=int(obs.get("day",0)); remaining=30-day
    money=float(me.get("money",0) or 0)
    tiles=me.get("tiles",[])
    unlocked=occupied=0
    for row in tiles:
        for tile in row:
            if tile=="LOCKED": continue
            unlocked+=1
            if tile is not None: occupied+=1

    oi=snap.get("origin_internal",{}) or {}
    strategy_name=oi.get("strategy_name")
    strategy=strong_origin.STRATEGIES.get(strategy_name,{})
    reserve=float(strategy.get("reserve_base",0) or 0)+20*occupied
    occupancy=(occupied/unlocked) if unlocked else 1.0
    occupancy_target=float(strategy.get("occupancy_target",1.0) or 1.0)
    quadrants=len(me.get("unlocked_quadrants",[]))
    land_cost={1:1000,2:2000,3:4000}.get(quadrants)

    land_open=bool(
        strategy_name not in ("LIQUID","ENDGAME")
        and land_cost
        and remaining>=9
        and occupancy>=occupancy_target
        and money-float(land_cost)>=reserve
    )

    market=oi.get("market",[]) or []
    actual_land=any(
        isinstance(a,(list,tuple)) and len(a)>=1 and a[0]=="BUY_LAND"
        for a in market
    )

    return {
        "turn":int(snap.get("turn")),
        "day":day,
        "LAND_policy_open":land_open,
        "actual_BUY_LAND":actual_land,
        "market":market,
    }


def play(seed,seat):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.reset_telemetry()
    rows=[]
    turn=-1

    def observed(obs):
        nonlocal turn
        turn+=1
        act=agent.agent(obs)
        if START<=turn<=END:
            rows.append(classify(obs,latest_snapshot()))
        return act

    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    return rows


def first_true(rows,key):
    for r in rows:
        if r.get(key):
            return r["turn"]
    return None


def main():
    cases=[]
    for seed,seat in CASES:
        rows=play(seed,seat)
        tau_open=first_true(rows,"LAND_policy_open")
        tau_buy=first_true(rows,"actual_BUY_LAND")
        realized = (
            None if tau_open is None
            else bool(tau_buy is not None and tau_buy>=tau_open)
        )

        cases.append({
            "seed":seed,
            "seat":seat,
            "group":"land" if (seed,seat) in LAND else "seed3",
            "tau_LAND_open":tau_open,
            "tau_BUY_LAND":tau_buy,
            "delay_open_to_buy":(
                None if tau_open is None or tau_buy is None else tau_buy-tau_open
            ),
            "realized":realized,
        })

    opened=[r for r in cases if r["tau_LAND_open"] is not None]
    realized=[r for r in opened if r["realized"] is True]
    not_realized=[r for r in opened if r["realized"] is False]

    out={
        "schema":"land-realized-gate.v0",
        "policy_mutated":False,
        "question":"Does LAND_policy_open lead to actual BUY_LAND?",
        "window":[START,END],
        "cases":cases,
        "summary":{
            "case_count":len(cases),
            "opened_count":len(opened),
            "realized_count":len(realized),
            "open_but_not_realized_count":len(not_realized),
            "no_open_count":len(cases)-len(opened),
        },
        "boundary":"Fills Realized Gate only. No terminal or direction interpretation."
    }

    Path("land_realized_gate_v0.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8"
    )

    print("LAND_REALIZED_GATE_V0 "+json.dumps(out["summary"],separators=(",",":")))
    print("LAND_REALIZED_GATE_ROWS "+json.dumps(cases,separators=(",",":")))


if __name__=="__main__":
    main()
