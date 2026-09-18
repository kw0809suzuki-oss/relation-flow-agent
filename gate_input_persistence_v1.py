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
            oi=s.get("origin_integration",{}) or {}
            gf=s.get("growth_field",{}) or {}
            out.append({
                "turn":s.get("turn"),"day":s.get("day"),
                "target":s.get("target"),"feed_carry":s.get("feed_carry"),
                "resonance":s.get("resonance"),"gate":s.get("gate"),
                "effective_gate":s.get("effective_gate"),"gate_margin":s.get("gate_margin"),
                "raw_opportunity":s.get("raw_opportunity"),"opportunity":s.get("opportunity"),
                "gate_scale":oi.get("gate_scale"),
                "native_strength":oi.get("native_strength"),
                "context_reliability":oi.get("context_reliability"),
                "role_reliability":oi.get("role_reliability"),
                "field_evidence":oi.get("field_evidence"),
                "field_alignment":oi.get("field_alignment"),
                "aligned_evidence":oi.get("aligned_evidence"),
                "opposed_evidence":oi.get("opposed_evidence"),
                "field_phase":oi.get("field_phase"),
                "commitment":oi.get("commitment"),
                "field_axis_relation":oi.get("field_axis_relation"),
                "opponent_cycle":s.get("opponent_cycle"),
                "growth_field":gf,
                "mode":s.get("mode"),
                "money":s.get("money"),"wheat":s.get("wheat"),"land":s.get("land"),
                "cooldown":(s.get("gate_conditions",{}) or {}).get("cooldown"),
                "probe_age":(s.get("gate_conditions",{}) or {}).get("probe_age"),
            })
    return out

rows=[]
for seed,seat in CASES:
    rows.append({
        "seed":seed,"seat":seat,
        "group":"land_reinvest" if (seed,seat) in LAND else "seed3",
        "trace":play(seed,seat)
    })

Path("gate_input_persistence_v1.json").write_text(
    json.dumps({"schema":"gate-input-persistence.v1","policy_mutated":False,"turns":[98,108],"cases":rows},ensure_ascii=False,indent=2)+"\n",
    encoding="utf-8"
)
print("GATE_INPUT_PERSISTENCE_V1",len(rows))
