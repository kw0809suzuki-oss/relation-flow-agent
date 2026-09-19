#!/usr/bin/env python3
import json, os
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import turn108_wheat3_suppress_v1 as exp

OPP=base.OPPONENT
BOUNDARY=[(4129,1),(4130,0),(4131,1),(4147,1),(4149,1),(4151,1),(4158,0),
          (4142,0),(4143,1),(4144,0),(4152,0),(4156,0),(4161,1)]
FRESH=[(4302+i,i%2) for i in range(30)]

def play(agent_fn,seed,seat,reset=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    baseline.reset_telemetry()
    if reset: reset()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    ps=[OPP,OPP]; ps[seat]=agent_fn
    env.run(ps)
    rewards=[float(s.reward) for s in env.state]
    trace=baseline.get_trace()
    snaps=trace["body"]["observe"]["body"]["snapshots"]
    land_open_turn=None
    for s in snaps:
        oi=s.get("origin_internal",{}) or {}
        if any(isinstance(a,(list,tuple)) and a and a[0]=="BUY_LAND" for a in (oi.get("market",[]) or [])):
            land_open_turn=s.get("turn")
            break
    return rewards[seat],rewards[seat]-rewards[1-seat],land_open_turn

def run(cases):
    rows=[]
    for seed,seat in cases:
        b,bm,bl=play(baseline.agent,seed,seat)
        e,em,el=play(exp.agent,seed,seat,exp.reset_experiment)
        acts=exp.get_activations()
        rows.append({
            "seed":seed,"seat":seat,
            "activation_count":len(acts),
            "activations":acts,
            "baseline_land_first":bl,
            "exp_land_first":el,
            "land_turn_diff":None if bl is None or el is None else el-bl,
            "baseline_self":b,"exp_self":e,"self_diff":e-b,
            "baseline_margin":bm,"exp_margin":em,"margin_diff":em-bm,
        })
    n=len(rows)
    summary={
        "case_count":n,
        "activated_cases":sum(r["activation_count"]>0 for r in rows),
        "activation_count":sum(r["activation_count"] for r in rows),
        "land_changed_cases":sum(r["baseline_land_first"]!=r["exp_land_first"] for r in rows),
        "improved":sum(r["self_diff"]>0 for r in rows),
        "worsened":sum(r["self_diff"]<0 for r in rows),
        "equal":sum(r["self_diff"]==0 for r in rows),
        "mean_self_diff":sum(r["self_diff"] for r in rows)/n,
        "mean_margin_diff":sum(r["margin_diff"] for r in rows)/n,
    }
    return rows,summary

boundary,boundary_summary=run(BOUNDARY)
fresh,fresh_summary=run(FRESH)
out={
  "schema":"turn108-wheat3-suppress.v1",
  "intervention":"remove only BUY_SEED WHEAT 3 at turn108",
  "reachability":{"target":"BUY_SEED WHEAT 3","expected_path":"cash +30 retained -> possible LAND recovery timing change -> terminal","required":"activation_count>0 and target_removed=True"},
  "boundary13":{"cases":boundary,"summary":boundary_summary},
  "fresh30":{"cases":fresh,"summary":fresh_summary}
}
open("turn108_wheat3_suppress_v1.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print("BOUNDARY13",json.dumps(boundary_summary,separators=(",",":")))
print("FRESH30",json.dumps(fresh_summary,separators=(",",":")))
