#!/usr/bin/env python3
"""Abstraction Transmission -> Model Candidate v0.

Flow-chan transmits one semantic abstraction. No hand-built Evaluation /
Comparison / Selection / Direction chain is enabled.

Treatment activates a model-generated interpretation of the abstraction.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"abstraction_transmission_model_candidate_v0_{SEED}.json")

def configure(transmit=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"

    # Disable the manually built reasoning chain.
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

    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(transmit=False):
    configure(transmit)
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
            "applied_flow_abstraction":s.get("applied_flow_abstraction"),
            "model_received":bool(internal.get("option_preservation_received",False)),
            "immediate_planting_surface":internal.get("immediate_planting_surface"),
            "existing_seed_commitment":internal.get("existing_seed_commitment"),
            "new_seed_commitment_budget_remaining":internal.get("new_seed_commitment_budget_remaining"),
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
    control_by_turn={x["turn"]:x for x in c["snapshots"]}

    received=sum(1 for x in t["snapshots"] if x.get("model_received"))
    action_changed=0
    examples=[]
    for y in t["snapshots"]:
        x=control_by_turn.get(y["turn"])
        if not x:
            continue
        if x.get("action") != y.get("action"):
            action_changed += 1
            if len(examples)<10:
                examples.append({
                    "turn":y.get("turn"),
                    "day":y.get("day"),
                    "control_action":x.get("action"),
                    "treatment_action":y.get("action"),
                    "planting_surface":y.get("immediate_planting_surface"),
                    "existing_seed_commitment":y.get("existing_seed_commitment"),
                    "remaining_new_seed_budget":y.get("new_seed_commitment_budget_remaining"),
                })

    payload={
        "schema":"kaggriculture.abstraction-transmission-model-candidate.v0",
        "seed":SEED,
        "seat":SEAT,
        "model_received_abstraction_turns":received,
        "action_changed_turns":action_changed,
        "terminal_control_self":c["self"],
        "terminal_treatment_self":t["self"],
        "terminal_self_diff":t["self"]-c["self"],
        "terminal_margin_diff":t["margin"]-c["margin"],
        "action_change_examples":examples,
        "boundary":[
            "Flow-chan transmits abstraction only; it does not evaluate, compare, select, direct, or rewrite actions.",
            "The treatment policy is a model-generated interpretation of Option Preservation, not evidence.",
            "Control and treatment both generate the same outer abstraction; only treatment exposes it to the model body.",
            "Manual candidate evaluation/comparison/selection/direction machinery is disabled in both arms.",
            "A bad terminal result rejects this interpretation, not the abstraction in general."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print("ABSTRACTION_TRANSMISSION_MODEL_CANDIDATE_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str))

if __name__=="__main__":
    main()
