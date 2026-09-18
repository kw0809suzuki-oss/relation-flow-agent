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

def score_sep(scores):
    vals=sorted([float(v) for v in (scores or {}).values()], reverse=True)
    if len(vals)<2: return 0.0
    return max(0.0, vals[0]-vals[1])/1.5

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
            out.append({
                "turn":s.get("turn"),
                "day":s.get("day"),
                "distortion":float(oi.get("distortion",0.0) or 0.0),
                "counter_weight":float(oi.get("counter_weight",0.0) or 0.0),
                "counter_opportunity":float(oi.get("counter_opportunity",0.0) or 0.0),
                "score_separation":score_sep(oi.get("scores",{})),
                "scores":oi.get("scores",{}),
                "native_strength":(s.get("origin_integration",{}) or {}).get("native_strength"),
                "strategy_name":oi.get("strategy_name"),
                "targets":oi.get("targets"),
            })
    return out

rows=[]
for seed,seat in CASES:
    rows.append({
        "seed":seed,"seat":seat,
        "group":"land_reinvest" if (seed,seat) in LAND else "seed3",
        "trace":play(seed,seat)
    })

Path("native_strength_components_v1.json").write_text(
    json.dumps({"schema":"native-strength-components.v1","policy_mutated":False,"turns":[98,108],"cases":rows},ensure_ascii=False,indent=2)+"\n",
    encoding="utf-8"
)
print("NATIVE_STRENGTH_COMPONENTS_V1",len(rows))
