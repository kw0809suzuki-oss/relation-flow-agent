#!/usr/bin/env python3
"""Model Selection -> Direction -> Action Probe v0.

A/B:
- Control: Lens + Evaluation + Comparison + Selection + Direction representation.
- Treatment: same + model re-reads state through its own Direction before Action generation.

The direction is model-side. Flow-chan still supplies only the lens/context.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"model_selection_direction_v0_{SEED}.json")

def configure(use_direction=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    os.environ["ORIGIN_EVALUATION_LENS"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_SELECTION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_DIRECTION"]="1"
    os.environ["ORIGIN_MODEL_SELECTION_GUIDED_GENERATION"]="0"
    os.environ["ORIGIN_MODEL_SELECTION_TO_ACTION"]="0"
    os.environ["ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]="1" if use_direction else "0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(use_direction=False):
    configure(use_direction)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    out=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14:
            continue
        current=dict(s.get("origin_integration_current",{}) or {})
        applied=dict(s.get("applied_origin_integration",{}) or {})
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "selection":current.get("candidate_selection"),
            "direction":current.get("candidate_direction"),
            "applied_direction":applied.get("candidate_direction"),
            "action":s.get("action"),
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

    direction_generated=0
    applied_direction=0
    action_changed=0
    examples=[]

    for y in t["snapshots"]:
        x=by_turn.get(y["turn"])
        if not x:
            continue
        if y.get("direction"):
            direction_generated+=1
        if y.get("applied_direction"):
            applied_direction+=1
        if x.get("action")!=y.get("action"):
            action_changed+=1
            if len(examples)<8:
                examples.append({
                    "turn":y.get("turn"),
                    "day":y.get("day"),
                    "selection":y.get("selection"),
                    "direction":y.get("applied_direction"),
                    "control_action":x.get("action"),
                    "treatment_action":y.get("action"),
                })

    payload={
        "schema":"kaggriculture.model-selection-direction.v0",
        "seed":SEED,
        "seat":SEAT,
        "direction_generated_turns":direction_generated,
        "applied_direction_context_turns":applied_direction,
        "action_changed_turns":action_changed,
        "terminal_control_self":c["self"],
        "terminal_treatment_self":t["self"],
        "terminal_self_diff":t["self"]-c["self"],
        "terminal_margin_diff":t["margin"]-c["margin"],
        "action_change_examples":examples,
        "boundary":[
            "Flow-chan still supplies only abstraction/lens/context.",
            "Selection and Direction are model-side.",
            "Direction is a hypothesis for reading State, not an externally selected Action.",
            "Treatment rotates one unit of the existing crop-target occupancy budget toward the model-selected crop; total target occupancy is preserved.",
            "No scalar score, fixed weight, total ranking, or explicit Action instruction is introduced.",
            "If Action changes, evaluate Battle before deeper internal analysis."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MODEL_SELECTION_DIRECTION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
