#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

LAND={(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0)}
SEED={(4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)}
CASES=sorted(LAND|SEED)
OPP=base.OPPONENT

def latest_snapshot():
    return agent.get_trace()["body"]["observe"]["body"]["snapshots"][-1]

def summarize_action(snapshot):
    oi=snapshot.get("origin_internal",{}) or {}
    market=oi.get("market",[]) or []
    out=[]
    for a in market:
        if not isinstance(a,(list,tuple)) or not a: continue
        out.append(list(a))
    return out

def play(seed,seat):
    base._configure_baseline(); os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"; agent.reset_telemetry()
    rows={}; turn=-1
    def observed(obs):
        nonlocal turn
        turn+=1
        act=agent.agent(obs)
        if turn in (108,109):
            s=latest_snapshot()
            rows[turn]={
                "turn":turn,
                "money":float(s.get("money",0) or 0),
                "action":summarize_action(s),
                "shed_sig":s.get("shed_sig"),
                "inv_sig":s.get("inv_sig"),
                "tile_sig":s.get("tile_sig"),
                "day":s.get("day"),
            }
        return act
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    r108=rows.get(108,{}); r109=rows.get(109,{})
    return {
        "money_108":r108.get("money"),
        "money_109":r109.get("money"),
        "delta_money":None if r108.get("money") is None or r109.get("money") is None else r109["money"]-r108["money"],
        "actual_108":r108.get("action"),
        "actual_109":r109.get("action"),
        "shed_changed":r108.get("shed_sig")!=r109.get("shed_sig"),
        "inventory_changed":r108.get("inv_sig")!=r109.get("inv_sig"),
        "tiles_changed":r108.get("tile_sig")!=r109.get("tile_sig"),
    }

cases=[]
for seed,seat in CASES:
    cases.append({
      "seed":seed,"seat":seat,
      "group":"land" if (seed,seat) in LAND else "seed3",
      **play(seed,seat)
    })

out={"schema":"cash-divergence-transition.v1","policy_mutated":False,"transition":"108->109","cases":cases}
Path("cash_divergence_transition_v1.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("CASH_DIVERGENCE_TRANSITION_V1",len(cases))
