#!/usr/bin/env python3
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"coarse_boundary_hysteresis_v0_{SEED}.json")

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

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent; env.run(players)
    rewards=[float(s.reward) for s in env.state]
    rows=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        internal=dict(s.get("origin_internal",{}) or {})
        rows.append({
          "turn":s.get("turn"),
          "choice":internal.get("model_guidance_choice"),
          "regime":internal.get("coarse_regime"),
          "boundary_changed":bool(internal.get("coarse_boundary_changed",False)),
          "pending_regime":internal.get("coarse_pending_regime"),
          "pending_count":internal.get("coarse_pending_count"),
          "action":s.get("action")
        })
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"rows":rows}

def summarize(x):
    return {
      "self":x["self"],"margin":x["margin"],
      "boundary_changes":sum(1 for r in x["rows"] if r["boundary_changed"]),
      "choice_counts":dict(Counter(str(r.get("choice") or "none") for r in x["rows"])),
      "regime_counts":dict(Counter(str(r.get("regime") or "none") for r in x["rows"])),
    }

def main():
    coarse=play("coarse_boundary_guidance")
    hyst=play("coarse_boundary_hysteresis")
    cb={r["turn"]:r for r in coarse["rows"]}
    payload={
      "schema":"kaggriculture.coarse-boundary-hysteresis.v0",
      "seed":SEED,"seat":SEAT,
      "coarse":summarize(coarse),
      "hysteresis":summarize(hyst),
      "hysteresis_vs_coarse":{
        "self_diff":hyst["self"]-coarse["self"],
        "margin_diff":hyst["margin"]-coarse["margin"],
        "action_changed_turns":sum(1 for r in hyst["rows"] if r["turn"] in cb and cb[r["turn"]].get("action")!=r.get("action")),
        "boundary_change_diff":sum(1 for r in hyst["rows"] if r["boundary_changed"])-sum(1 for r in coarse["rows"] if r["boundary_changed"])
      },
      "hypothesis_status":"working_hypothesis"
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
