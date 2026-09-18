#!/usr/bin/env python3
"""Fresh matched A/B for Value Bundle Flow Control v0."""
import json, os, statistics
from kaggle_environments import make
import export_scale_baseline_v1 as base
import whole_flow_control_agent as agent

OPPONENT=base.OPPONENT
CASES=tuple((4122+i, i%2) for i in range(10))

def play(seed,seat,enabled):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1" if enabled else "0"
    agent.reset_telemetry()
    env=make("kaggriculture",configuration={"seed":seed},debug=False)
    players=[OPPONENT,OPPONENT]
    players[seat]=agent.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    t=agent.get_telemetry()
    return {
      "seed":seed,"seat":seat,
      "self":rewards[seat],"opponent":rewards[1-seat],
      "margin":rewards[seat]-rewards[1-seat],
      "activations":t.get("bundle_flow_v0_turns",0),
      "suppressed_expansions":t.get("bundle_flow_v0_suppressed_expansions",0),
      "supported_turns":t.get("bundle_flow_v0_supported_turns",0),
    }

def main():
    rows=[]
    for seed,seat in CASES:
        b=play(seed,seat,False)
        v=play(seed,seat,True)
        rows.append({
          "seed":seed,"seat":seat,
          "baseline":b,"control":v,
          "self_diff":v["self"]-b["self"],
          "margin_diff":v["margin"]-b["margin"],
        })
    ds=[r["self_diff"] for r in rows]
    md=[r["margin_diff"] for r in rows]
    out={
      "schema":"bundle-flow-control-v0.fresh10",
      "objective":"terminal self money",
      "cases":rows,
      "summary":{
        "n":len(rows),
        "baseline_mean_self":statistics.mean(r["baseline"]["self"] for r in rows),
        "control_mean_self":statistics.mean(r["control"]["self"] for r in rows),
        "mean_self_diff":statistics.mean(ds),
        "mean_margin_diff":statistics.mean(md),
        "improved":sum(x>0 for x in ds),
        "worsened":sum(x<0 for x in ds),
        "equal":sum(x==0 for x in ds),
        "activated_matches":sum(r["control"]["activations"]>0 for r in rows),
        "suppressed_expansions":sum(r["control"]["suppressed_expansions"] for r in rows),
      },
      "boundary":[
        "same-seed/same-seat matched A/B",
        "future sale value is not counted as current cash by the v0 gate",
        "v0 changes only livestock expansion/feed-carry at the existing G15 control surface"
      ]
    }
    open("bundle_flow_control_v0_fresh10.json","w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("BUNDLE_FLOW_CONTROL_V0 "+json.dumps(out["summary"],separators=(",",":")))

if __name__=="__main__": main()
