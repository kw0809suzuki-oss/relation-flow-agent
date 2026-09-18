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
TURNS=range(98,109)

def snaps(trace):
    return trace["body"]["observe"]["body"]["snapshots"]

def top2(scores):
    items=sorted(((str(k),float(v)) for k,v in (scores or {}).items()), key=lambda x:x[1], reverse=True)
    while len(items)<2: items.append((None,0.0))
    return items[:2]

def play(seed,seat):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    agent.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    def observed(obs): return agent.agent(obs)
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    out=[]
    for s in snaps(agent.get_trace()):
        if int(s.get("turn",-1)) in TURNS:
            oi=s.get("origin_internal",{}) or {}
            scores=oi.get("scores",{}) or {}
            a,b=top2(scores)
            out.append({
                "turn":s.get("turn"),
                "top1_crop":a[0],"top1_score":a[1],
                "top2_crop":b[0],"top2_score":b[1],
                "separation":a[1]-b[1],
                "scores":scores,
                "targets":oi.get("targets"),
                "strategy_name":oi.get("strategy_name"),
            })
    return out

rows=[]
for seed,seat in CASES:
    rows.append({
        "seed":seed,"seat":seat,
        "group":"land_reinvest" if (seed,seat) in LAND else "seed3",
        "trace":play(seed,seat)
    })

Path("top2_crop_score_boundary_v1.json").write_text(
    json.dumps({"schema":"top2-crop-score-boundary.v1","policy_mutated":False,"turns":[98,108],"cases":rows},ensure_ascii=False,indent=2)+"\n",
    encoding="utf-8"
)
print("TOP2_CROP_SCORE_BOUNDARY_V1",len(rows))
