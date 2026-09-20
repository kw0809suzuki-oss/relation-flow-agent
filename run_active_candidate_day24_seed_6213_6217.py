#!/usr/bin/env python3
"""Active Candidate validation batch: Day24 WHEAT seed suppression.

Five fresh Battles. Keep the candidate fixed and judge only whether the same
direction replicates. No causal deep dive and no formal Rule adoption.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

CASES=[(6213,0),(6214,1),(6215,0),(6216,1),(6217,0)]
OPPONENT=base.OPPONENT
OUT=Path("active_candidate_day24_seed_6213_6217.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(seed,seat,suppress):
    configure()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    closes={}
    last_day=None
    last_state=None
    removed=[]

    def agent(obs):
        nonlocal last_day,last_state
        day=int(obs.get("day",0) or 0)
        state=observe_state(obs)
        if last_day is not None and day!=last_day and last_state is not None:
            closes[last_day]=last_state
        last_day=day
        last_state=state

        actions=combat.agent(obs)
        if suppress and day==24 and isinstance(actions,dict):
            market=list(actions.get("market",[]) or [])
            kept=[]
            for a in market:
                if isinstance(a,(list,tuple)) and len(a)>=2 and a[0]=="BUY_SEED" and a[1]=="WHEAT":
                    removed.append(copy.deepcopy(a))
                else:
                    kept.append(a)
            if len(kept)!=len(market):
                actions=copy.deepcopy(actions)
                actions["market"]=kept
        return actions

    players=[OPPONENT,OPPONENT]
    players[seat]=agent
    env.run(players)

    if last_day is not None and last_state is not None:
        closes[last_day]=last_state

    rewards=[float(x.reward) for x in env.state]
    end=closes[29]
    return {
        "terminal":{
            "self":rewards[seat],
            "opponent":rewards[1-seat],
            "margin":rewards[seat]-rewards[1-seat],
        },
        "removed_count":len(removed),
        "terminal_state":{
            "seed_wheat":end["flow_inputs"]["seed_inventory"]["WHEAT"],
            "planted":end["capacity"]["planted_tiles"],
            "harvestable":end["flow_outputs"]["harvestable_tiles"],
        }
    }

def main():
    rows=[]
    for seed,seat in CASES:
        baseline=play(seed,seat,False)
        variant=play(seed,seat,True)
        rows.append({
            "seed":seed,
            "seat":seat,
            "baseline":baseline,
            "variant":variant,
            "diff":{
                "terminal_self":variant["terminal"]["self"]-baseline["terminal"]["self"],
                "terminal_margin":variant["terminal"]["margin"]-baseline["terminal"]["margin"],
                "terminal_seed_wheat":variant["terminal_state"]["seed_wheat"]-baseline["terminal_state"]["seed_wheat"],
                "terminal_planted":variant["terminal_state"]["planted"]-baseline["terminal_state"]["planted"],
                "terminal_harvestable":variant["terminal_state"]["harvestable"]-baseline["terminal_state"]["harvestable"],
            }
        })

    payload={
        "schema":"kaggriculture.active-candidate.day24-seed.v0",
        "candidate":{
            "name":"day24_wheat_seed_suppression",
            "status":"active_candidate",
            "adoption":"proposed",
            "formal_rule":False,
            "purpose":"test same-direction replication on fresh Battles"
        },
        "cases":rows,
        "judgment":{
            "same_form":"strengthen active candidate",
            "mixed_effect":"hold with boundary",
            "any_worsening":"retain possibility that Day24 vicinity is too broad"
        },
        "boundary":[
            "Variant is fixed across all five Battles.",
            "Evaluate only terminal self, margin, terminal seed, planted, and harvestable differences.",
            "Do not decompose causes during this batch.",
            "Active Candidate is not a formal Rule and is not auto-adopted."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACTIVE_CANDIDATE_DAY24_SEED "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
