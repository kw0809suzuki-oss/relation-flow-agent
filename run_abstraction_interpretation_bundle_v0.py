#!/usr/bin/env python3
"""Abstraction -> Interpretation Bundle -> Battle v0.

One Flow-chan abstraction is transmitted.
The model exposes three different operational interpretations.
The framework does not select among them before Battle.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"abstraction_interpretation_bundle_v0_{SEED}.json")

INTERPRETATIONS={
    "capacity_aligned":"new seed commitment bounded by near-term planting surface",
    "alternative_affordability":"preserve cash to keep other viable crop directions affordable",
    "staged_commitment":"commit one seed unit per crop per turn",
}

def configure(transmit=False, mode="capacity_aligned"):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"

    # The previous hand-built reasoning chain stays off.
    os.environ["ORIGIN_EVALUATION_LENS"]="0"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="0"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"]="0"
    os.environ["ORIGIN_MODEL_CANDIDATE_SELECTION"]="0"
    os.environ["ORIGIN_MODEL_CANDIDATE_DIRECTION"]="0"
    os.environ["ORIGIN_MODEL_SELECTION_GUIDED_GENERATION"]="0"
    os.environ["ORIGIN_MODEL_SELECTION_TO_ACTION"]="0"
    os.environ["ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"

    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1" if transmit else "0"
    os.environ["ORIGIN_ABSTRACTION_INTERPRETATION"]=mode

    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(transmit=False, mode="capacity_aligned"):
    configure(transmit,mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    out=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14:
            continue
        internal=dict(s.get("origin_internal",{}) or {})
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "action":s.get("action"),
            "model_received":bool(internal.get("option_preservation_received",False)),
            "interpretation_mode":internal.get("interpretation_mode"),
            "planting_surface":internal.get("immediate_planting_surface"),
            "existing_seed_commitment":internal.get("existing_seed_commitment"),
            "new_seed_budget":internal.get("new_seed_commitment_budget_remaining"),
            "alternative_cash_floor":internal.get("alternative_cash_floor"),
        })
    return {
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "snapshots":out,
    }

def summarize_variant(control, treatment, mode):
    by_turn={x["turn"]:x for x in control["snapshots"]}
    received=sum(1 for x in treatment["snapshots"] if x.get("model_received"))
    changed=[]
    for y in treatment["snapshots"]:
        x=by_turn.get(y["turn"])
        if x is not None and x.get("action") != y.get("action"):
            changed.append({
                "turn":y.get("turn"),
                "day":y.get("day"),
                "control_action":x.get("action"),
                "treatment_action":y.get("action"),
            })
    return {
        "interpretation":mode,
        "description":INTERPRETATIONS[mode],
        "model_received_turns":received,
        "action_changed_turns":len(changed),
        "terminal_self":treatment["self"],
        "terminal_margin":treatment["margin"],
        "terminal_self_diff_vs_control":treatment["self"]-control["self"],
        "terminal_margin_diff_vs_control":treatment["margin"]-control["margin"],
        "action_change_examples":changed[:6],
    }

def main():
    control=play(False,"capacity_aligned")
    variants={}
    for mode in INTERPRETATIONS:
        variants[mode]=summarize_variant(control,play(True,mode),mode)

    payload={
        "schema":"kaggriculture.abstraction-interpretation-bundle.v0",
        "seed":SEED,
        "seat":SEAT,
        "control_terminal_self":control["self"],
        "control_terminal_margin":control["margin"],
        "interpretations":variants,
        "boundary":[
            "Flow-chan transmits one abstraction only.",
            "All interpretations are model-side generated hypotheses.",
            "No interpretation is selected before Battle.",
            "Manual Evaluation / Comparison / Selection / Direction machinery remains disabled.",
            "A losing interpretation does not falsify the parent abstraction.",
            "If multiple interpretations remain plausible, re-enter from their observed Battle differences."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print("ABSTRACTION_INTERPRETATION_BUNDLE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str))

if __name__=="__main__":
    main()
