#!/usr/bin/env python3
import json, os
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as control
import strawberry_score_flip_v1 as flip

OPP=base.OPPONENT
BOUNDARY=[(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0),
          (4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)]
# Fresh and disjoint from earlier 4102..4161 work.
FRESH=[(4202+i,i%2) for i in range(30)]

def play(agent_fn,seed,seat,reset=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    control.reset_telemetry()
    if reset: reset()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    ps=[OPP,OPP]; ps[seat]=agent_fn
    env.run(ps)
    rewards=[float(s.reward) for s in env.state]
    return rewards[seat],rewards[seat]-rewards[1-seat]

def run_cases(cases):
    rows=[]
    for seed,seat in cases:
        b,bm=play(control.agent,seed,seat)
        f,fm=play(flip.agent,seed,seat,flip.reset_experiment)
        acts=flip.get_activations()
        rows.append({"seed":seed,"seat":seat,"activation_count":len(acts),"activations":acts,
                     "baseline_self":b,"flip_self":f,"self_diff":f-b,
                     "baseline_margin":bm,"flip_margin":fm,"margin_diff":fm-bm})
    def summary(rows):
        n=len(rows)
        return {"case_count":n,"activated_cases":sum(r["activation_count"]>0 for r in rows),
                "activation_count":sum(r["activation_count"] for r in rows),
                "mean_self_diff":sum(r["self_diff"] for r in rows)/n,
                "mean_margin_diff":sum(r["margin_diff"] for r in rows)/n,
                "improved":sum(r["self_diff"]>0 for r in rows),
                "worsened":sum(r["self_diff"]<0 for r in rows),
                "equal":sum(r["self_diff"]==0 for r in rows)}
    return rows,summary(rows)

boundary,boundary_summary=run_cases(BOUNDARY)
fresh,fresh_summary=run_cases(FRESH)
out={"schema":"strawberry-score-flip.v1",
     "change":"Turn98-108 only: if 0 < WHEAT_score-STRAWBERRY_score <= 0.04, add +0.04 to STRAWBERRY score only",
     "boundary13":{"cases":boundary,"summary":boundary_summary},
     "fresh30":{"cases":fresh,"summary":fresh_summary}}
open("strawberry_score_flip_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print("BOUNDARY13",json.dumps(boundary_summary,separators=(",",":")))
print("FRESH30",json.dumps(fresh_summary,separators=(",",":")))
