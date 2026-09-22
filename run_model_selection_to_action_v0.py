#!/usr/bin/env python3
"""Model Selection -> Action Probe v0.

A/B:
- Control: Lens + Evaluation + Comparison + Model Selection.
- Treatment: same + model uses its own previous selection while generating action.

No new Flow-chan rule is added. The adapter never chooses a crop; it consumes
only the candidate already selected by the model.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"model_selection_to_action_v0_{SEED}.json")

def configure(action_use=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    os.environ["ORIGIN_EVALUATION_LENS"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_SELECTION"]="1"
    os.environ["ORIGIN_MODEL_SELECTION_TO_ACTION"]="1" if action_use else "0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(action_use=False):
    configure(action_use)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    out=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14:
            continue
        integ=dict(s.get("origin_integration_current",{}) or {})
        applied=dict(s.get("applied_origin_integration",{}) or {})
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "candidate_selection":integ.get("candidate_selection"),
            "applied_candidate_selection":applied.get("candidate_selection"),
            "final_action":s.get("action"),
        })
    return {
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "snapshots":out,
    }

def main():
    c=play(False)
    t=play(True)
    by_turn={x["turn"]:x for x in c["snapshots"]}

    selection_turns=0
    applied_selection_turns=0
    action_changed=0
    first_changes=[]

    for y in t["snapshots"]:
        x=by_turn.get(y["turn"])
        if not x:
            continue
        if y.get("candidate_selection"):
            selection_turns+=1
        if y.get("applied_candidate_selection"):
            applied_selection_turns+=1
        if x.get("final_action")!=y.get("final_action"):
            action_changed+=1
            if len(first_changes)<8:
                first_changes.append({
                    "turn":y.get("turn"),
                    "day":y.get("day"),
                    "selection":y.get("applied_candidate_selection"),
                    "control_action":x.get("final_action"),
                    "treatment_action":y.get("final_action"),
                })

    payload={
        "schema":"kaggriculture.model-selection-to-action.v0",
        "seed":SEED,
        "seat":SEAT,
        "selection_generated_turns":selection_turns,
        "applied_selection_context_turns":applied_selection_turns,
        "action_changed_turns":action_changed,
        "terminal_control_self":c["self"],
        "terminal_treatment_self":t["self"],
        "terminal_self_diff":t["self"]-c["self"],
        "terminal_margin_diff":t["margin"]-c["margin"],
        "action_change_examples":first_changes,
        "boundary":[
            "Flow-chan adds no new decision rule in this experiment.",
            "The model uses only its own prior candidate selection.",
            "No scalar score, fixed weight, total ranking, candidate invention, purchase quantity rewrite, or target rewrite.",
            "If Action changes, proceed directly to Battle effect before deeper internal analysis."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MODEL_SELECTION_TO_ACTION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
