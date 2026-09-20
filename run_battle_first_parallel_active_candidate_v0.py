#!/usr/bin/env python3
"""Battle-First parallel bundle worker.

One seed per job. Paired baseline vs fixed Active Candidate:
remove only Day24 BUY_SEED WHEAT.

Environment:
  BATTLE_SEED
  BATTLE_SEAT
  GITHUB_RUN_ID / GITHUB_SHA are recorded when available.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as combat
from judgment_capability_v1 import observe_state

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
VARIANT="day24_wheat_seed_suppression_v0"
OUT=Path(f"parallel_battle_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    combat.set_control_enabled(False)
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def play(suppress):
    configure()
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
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
    players[SEAT]=agent
    env.run(players)
    if last_day is not None and last_state is not None:
        closes[last_day]=last_state

    rewards=[float(x.reward) for x in env.state]
    end=closes[29]
    return {
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "removed_count":len(removed),
        "terminal_state":{
            "seed_wheat":end["flow_inputs"]["seed_inventory"]["WHEAT"],
            "planted":end["capacity"]["planted_tiles"],
            "harvestable":end["flow_outputs"]["harvestable_tiles"],
        }
    }

def main():
    baseline=play(False)
    variant=play(True)
    diff={
        "terminal_self":variant["terminal"]["self"]-baseline["terminal"]["self"],
        "terminal_margin":variant["terminal"]["margin"]-baseline["terminal"]["margin"],
        "terminal_seed_wheat":variant["terminal_state"]["seed_wheat"]-baseline["terminal_state"]["seed_wheat"],
        "terminal_planted":variant["terminal_state"]["planted"]-baseline["terminal_state"]["planted"],
        "terminal_harvestable":variant["terminal_state"]["harvestable"]-baseline["terminal_state"]["harvestable"],
    }
    direction="improved" if diff["terminal_self"]>0 else "worsened" if diff["terminal_self"]<0 else "equal"
    payload={
        "schema":"kaggriculture.battle-first.parallel-active-candidate.v0",
        "run_id":os.environ.get("GITHUB_RUN_ID"),
        "commit":os.environ.get("GITHUB_SHA"),
        "seed":SEED,
        "seat":SEAT,
        "variant":VARIANT,
        "baseline":baseline,
        "candidate_run":variant,
        "diff":diff,
        "direction":direction,
        "artifact":f"parallel-battle-{SEED}",
        "boundary":[
            "Variant and evaluation conditions are fixed for the full 20-Battle bundle.",
            "Baseline and Variant use the same seed, seat, opponent, and runtime configuration.",
            "No per-seed condition changes or causal deep dive.",
            "Equal is distinct from failure.",
            "Active Candidate remains proposed and is not auto-adopted."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PARALLEL_BATTLE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
