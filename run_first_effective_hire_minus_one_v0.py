#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"first_effective_hire_minus_one_v0_{SEED}.json")

def configure(mode):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]=mode
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snaps(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    rows=[]
    for s in snaps(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        i=dict(s.get("origin_internal",{}) or {})
        rows.append({
          "turn":s.get("turn"),
          "day":s.get("day"),
          "choice":i.get("model_guidance_choice"),
          "regime":i.get("coarse_regime"),
          "triggered":bool(i.get("first_effective_hire_minus_one_triggered",False)),
          "action":s.get("action")
        })
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"rows":rows}

def diff(a,b):
    return {"self_diff":b["self"]-a["self"],"margin_diff":b["margin"]-a["margin"]}

def main():
    current=play("objective_pressure_guidance")
    coarse=play("coarse_boundary_guidance")
    candidate=play("first_effective_hire_minus_one")
    by={r["turn"]:r for r in current["rows"]}
    trigger=[r for r in candidate["rows"] if r["triggered"]]
    changed=[r["turn"] for r in candidate["rows"] if r["turn"] in by and by[r["turn"]]["action"]!=r["action"]]
    payload={
      "schema":"kaggriculture.first-effective-hire-minus-one.v0",
      "seed":SEED,"seat":SEAT,
      "current":{"self":current["self"],"margin":current["margin"]},
      "coarse":{"self":coarse["self"],"margin":coarse["margin"]},
      "candidate":{"self":candidate["self"],"margin":candidate["margin"]},
      "candidate_vs_current":diff(current,candidate),
      "candidate_vs_coarse":diff(coarse,candidate),
      "trigger_count":len(trigger),
      "trigger_turns":[r["turn"] for r in trigger],
      "action_changed_turns_vs_current":len(changed),
      "first_action_changed_turn":changed[0] if changed else None,
      "hypothesis_status":"working_hypothesis"
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
