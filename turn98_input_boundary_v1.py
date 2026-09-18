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

def snaps(trace):
    return trace["body"]["observe"]["body"]["snapshots"]

def play(seed,seat,enabled):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1" if enabled else "0"
    agent.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    def observed(obs): return agent.agent(obs)
    ps=[OPP,OPP]; ps[seat]=observed
    env.run(ps)
    out=[]
    for s in snaps(agent.get_trace()):
        if 96 <= int(s.get("turn",-1)) <= 99:
            gf=s.get("growth_field",{}) or {}
            out.append({
              "turn":s.get("turn"),"day":s.get("day"),
              "money":s.get("money"),"R":s.get("R"),"E":s.get("E"),"W":s.get("W"),
              "W_alpha":s.get("W_alpha"),"resonance":s.get("resonance"),
              "gate":s.get("gate"),"effective_gate":s.get("effective_gate"),
              "gate_margin":s.get("gate_margin"),
              "raw_opportunity":s.get("raw_opportunity"),
              "opportunity":s.get("opportunity"),
              "growth_weight":s.get("growth_weight"),
              "opponent_cycle":s.get("opponent_cycle"),
              "growth_field":gf,
              "mode":s.get("mode"),"target":s.get("target"),"feed_carry":s.get("feed_carry")
            })
    return out

rows=[]
for seed,seat in CASES:
    rows.append({"seed":seed,"seat":seat,"group":"land_reinvest" if (seed,seat) in LAND else "seed3",
                 "baseline":play(seed,seat,False),"control":play(seed,seat,True)})
Path("turn98_input_boundary_v1.json").write_text(json.dumps({"schema":"turn98-input-boundary.v1","policy_mutated":False,"cases":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("TURN98_INPUT_BOUNDARY_V1",len(rows))
