#!/usr/bin/env python3
"""Model Selection-Guided Generation v0.

A/B:
- Control: Lens + Evaluation + Comparison + Model Selection.
- Treatment: same, but the model's own prior selection is consulted while
  generating seed-purchase and planting candidates.

Flow-chan adds no action rule. No scalar score, fixed weight, total ranking,
target rewrite, purchase quantity rewrite, or candidate invention is added.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"model_selection_guided_generation_v0_{SEED}.json")

def configure(guided=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    os.environ["ORIGIN_EVALUATION_LENS"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_SELECTION"]="1"
    os.environ["ORIGIN_MODEL_SELECTION_TO_ACTION"]="0"
    os.environ["ORIGIN_MODEL_SELECTION_GUIDED_GENERATION"]="1" if guided else "0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(guided=False):
    configure(guided)
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
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "selection":integ.get("candidate_selection"),
            "action":s.get("action"),
            "market":(s.get("action") or {}).get("market"),
            "farmer":(s.get("action") or {}).get("farmer"),
            "hands":(s.get("action") or {}).get("hands"),
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
    action_changed=0
    market_changed=0
    unit_changed=0
    examples=[]

    for y in t["snapshots"]:
        x=by_turn.get(y["turn"])
        if not x:
            continue
        if y.get("selection"):
            selection_turns+=1
        if x.get("action")!=y.get("action"):
            action_changed+=1
            if x.get("market")!=y.get("market"):
                market_changed+=1
            if x.get("farmer")!=y.get("farmer") or x.get("hands")!=y.get("hands"):
                unit_changed+=1
            if len(examples)<8:
                examples.append({
                    "turn":y.get("turn"),
                    "day":y.get("day"),
                    "selection":y.get("selection"),
                    "control_action":x.get("action"),
                    "treatment_action":y.get("action"),
                })

    payload={
        "schema":"kaggriculture.model-selection-guided-generation.v0",
        "seed":SEED,
        "seat":SEAT,
        "selection_generated_turns":selection_turns,
        "action_changed_turns":action_changed,
        "market_changed_turns":market_changed,
        "unit_changed_turns":unit_changed,
        "terminal_control_self":c["self"],
        "terminal_treatment_self":t["self"],
        "terminal_self_diff":t["self"]-c["self"],
        "terminal_margin_diff":t["margin"]-c["margin"],
        "action_change_examples":examples,
        "boundary":[
            "Flow-chan adds no action rule.",
            "Treatment exposes the model's own prior selection during action candidate generation.",
            "Selected crop only changes ordering among already-generatable seed and planting candidates.",
            "No scalar score, fixed weight, total ranking, target rewrite, purchase quantity rewrite, or candidate invention.",
            "If Action changes, Battle effect is evaluated before deeper internal analysis."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MODEL_SELECTION_GUIDED_GENERATION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
