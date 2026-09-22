#!/usr/bin/env python3
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"coarse_boundary_guidance_v0_{SEED}.json")

def configure(mode=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1" if mode else "0"
    os.environ["ORIGIN_GUIDANCE_MODE"]=mode or "none"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode=None):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    rows=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        internal=dict(s.get("origin_internal",{}) or {})
        rows.append({
          "turn":s.get("turn"),
          "day":s.get("day"),
          "action":s.get("action"),
          "choice":internal.get("model_guidance_choice"),
          "reason":internal.get("model_guidance_reason"),
          "regime":internal.get("coarse_regime"),
          "boundary_changed":bool(internal.get("coarse_boundary_changed",False)),
        })
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"rows":rows}

def compare(control,treat,label):
    cb={x["turn"]:x for x in control["rows"]}
    choices=Counter(str(x.get("choice") or "none") for x in treat["rows"])
    regimes=Counter(str(x.get("regime") or "none") for x in treat["rows"])
    reasons=Counter(str(x.get("reason") or "none") for x in treat["rows"])
    return {
      "arm":label,
      "action_changed_turns":sum(1 for y in treat["rows"] if y["turn"] in cb and cb[y["turn"]].get("action")!=y.get("action")),
      "terminal_self_diff":treat["self"]-control["self"],
      "terminal_margin_diff":treat["margin"]-control["margin"],
      "choice_counts":dict(choices),
      "regime_counts":dict(regimes),
      "reason_counts":dict(reasons),
      "boundary_change_count":sum(1 for y in treat["rows"] if y.get("boundary_changed")),
    }

def main():
    control=play(None)
    current=play("objective_pressure_guidance")
    candidate=play("coarse_boundary_guidance")
    payload={
      "schema":"kaggriculture.coarse-boundary-guidance.v0",
      "seed":SEED,"seat":SEAT,
      "control_self":control["self"],"control_margin":control["margin"],
      "current_objective_pressure":compare(control,current,"current_objective_pressure"),
      "coarse_boundary_candidate":compare(control,candidate,"coarse_boundary_candidate"),
      "candidate_vs_current":{
        "self_diff":candidate["self"]-current["self"],
        "margin_diff":candidate["margin"]-current["margin"],
      },
      "boundary":[
        "Coarse-boundary behavior is a working hypothesis.",
        "Regime labels are operational probes, not established State ontology.",
        "Adoption depends on Battle, not explanatory elegance."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
