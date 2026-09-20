#!/usr/bin/env python3
"""High-Leverage Search Bundle v0.

Same native G17 baseline, same seed/seat/opponent.
Three minimal strategic interventions are compared independently:
- COW: suppress first BUY_ANIMAL/BUY_PRODUCT COW 1 once
- LAND: suppress first BUY_LAND once
- CLOSURE14: when remaining horizon <= 14, suppress expansion purchases

Purpose: screen Magnitude / Direction / Robustness, not adopt rules.
"""
import copy, json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import g17_agent as native

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"high_leverage_bundle_v0_{SEED}.json")
TERMINAL_DAY=30

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    native.set_probe_enabled(True)
    native.set_attribution_enabled(True)
    native.reset_telemetry()

def score(rewards):
    own=float(rewards[SEAT]); opp=float(rewards[1-SEAT])
    return {"self":own,"opponent":opp,"margin":own-opp}

def play(mode):
    configure()
    state={"cow_done":False,"land_done":False,"activations":[]}
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)

    def agent(obs):
        actions=native.agent(obs)
        if not isinstance(actions,dict):
            return actions
        day=int(obs.get("day",0) or 0)
        market=list(actions.get("market",[]) or [])
        revised=None
        removed=[]

        if mode=="cow" and not state["cow_done"]:
            for a in market:
                if isinstance(a,(list,tuple)) and len(a)>=3 and a[0] in ("BUY_ANIMAL","BUY_PRODUCT") and a[1]=="COW" and int(a[2])==1:
                    removed.append(copy.deepcopy(a))
            if removed:
                revised=copy.deepcopy(actions)
                revised["market"]=[a for a in market if not (
                    isinstance(a,(list,tuple)) and len(a)>=3 and a[0] in ("BUY_ANIMAL","BUY_PRODUCT") and a[1]=="COW" and int(a[2])==1
                )]
                state["cow_done"]=True

        elif mode=="land" and not state["land_done"]:
            removed=[copy.deepcopy(a) for a in market if isinstance(a,(list,tuple)) and len(a)>=1 and a[0]=="BUY_LAND"]
            if removed:
                revised=copy.deepcopy(actions)
                revised["market"]=[a for a in market if not (isinstance(a,(list,tuple)) and len(a)>=1 and a[0]=="BUY_LAND")]
                state["land_done"]=True

        elif mode=="closure14":
            remaining=TERMINAL_DAY-day
            if remaining<=14:
                def is_expansion(a):
                    if not isinstance(a,(list,tuple)) or not a:
                        return False
                    op=a[0]
                    if op in ("BUY_LAND","BUY_SEED","BUY_ANIMAL"):
                        return True
                    return op=="BUY_PRODUCT" and len(a)>1 and a[1]=="COW"
                removed=[copy.deepcopy(a) for a in market if is_expansion(a)]
                if removed:
                    revised=copy.deepcopy(actions)
                    revised["market"]=[a for a in market if not is_expansion(a)]

        if removed:
            state["activations"].append({"day":day,"removed":removed})
        return revised if revised is not None else actions

    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent
    env.run(players)
    rewards=[s.reward for s in env.state]
    return {"terminal":score(rewards),"activation_count":len(state["activations"]),"activation_days":sorted({x["day"] for x in state["activations"]})}

def main():
    baseline=play("baseline")
    variants={}
    for mode in ("cow","land","closure14"):
        result=play(mode)
        variants[mode]={
            **result,
            "diff_self":result["terminal"]["self"]-baseline["terminal"]["self"],
            "diff_margin":result["terminal"]["margin"]-baseline["terminal"]["margin"],
        }

    payload={
        "schema":"kaggriculture.high-leverage-search.bundle.v0",
        "seed":SEED,
        "seat":SEAT,
        "run_id":os.environ.get("GITHUB_RUN_ID"),
        "commit":os.environ.get("GITHUB_SHA"),
        "baseline":baseline,
        "variants":variants,
        "boundary":[
            "Same native G17 baseline, seed, seat, opponent, runtime config for all variants.",
            "Purpose is Magnitude / Direction / Robustness screening only.",
            "Large movement is not equivalent to a good direction.",
            "No variant is auto-adopted.",
            "No rescue conditions are added after seeing outcomes."
        ],
        "artifact":f"high-leverage-bundle-v0-{SEED}"
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HIGH_LEVERAGE_BUNDLE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
