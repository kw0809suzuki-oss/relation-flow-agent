#!/usr/bin/env python3
import json,os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as setup
import g17_agent as baseline
import wheat_market_netting_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=setup.OPPONENT
OUT=Path(f"wheat_market_netting_v0_{SEED}.json")

def configure(agent_mod):
    setup._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]="objective_pressure_guidance"
    if hasattr(agent_mod,"set_probe_enabled"): agent_mod.set_probe_enabled(True)
    if hasattr(agent_mod,"set_attribution_enabled"): agent_mod.set_attribution_enabled(True)
    if hasattr(agent_mod,"reset_telemetry"): agent_mod.reset_telemetry()

def run(agent_mod):
    configure(agent_mod)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=agent_mod.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    tel=agent_mod.get_telemetry() if hasattr(agent_mod,"get_telemetry") else {}
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"telemetry":tel}

def main():
    b=run(baseline)
    c=run(candidate)
    payload={
      "schema":"kaggriculture.wheat-market-netting.v0",
      "seed":SEED,"seat":SEAT,
      "baseline":b,"candidate":c,
      "delta_self":c["self"]-b["self"],
      "delta_margin":c["margin"]-b["margin"],
      "result":"improve" if c["self"]>b["self"] else ("worse" if c["self"]<b["self"] else "tie")
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
