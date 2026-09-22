#!/usr/bin/env python3
"""Model Candidate Evaluation Probe v0.

A/B:
- Control: OPTION_PRESERVATION abstraction + Evaluation Lens.
- Treatment: same Lens + model-side descriptive Candidate Evaluation.

No ranking, target rewrite, action rewrite, threshold, cap, or selection.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"model_candidate_evaluation_v0_{SEED}.json")

def configure(evaluate=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    os.environ["ORIGIN_EVALUATION_LENS"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="1" if evaluate else "0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(evaluate=False):
    configure(evaluate)
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
        integ=dict(s.get("origin_integration_current",{}) or {})
        ev=integ.get("candidate_evaluation")
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "strategy":internal.get("strategy_name"),
            "targets":internal.get("targets"),
            "best_crop":internal.get("best_crop"),
            "market":internal.get("market"),
            "final_action":s.get("action"),
            "lens_present":bool(integ.get("evaluation_lens_present")),
            "candidate_evaluation_present":bool(integ.get("candidate_evaluation_present")),
            "candidate_evaluation":ev,
            "candidate_ranking":integ.get("candidate_ranking"),
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
    evaluation_changed=0
    ranking_changed=0
    target_changed=0
    action_changed=0
    treatment_eval_turns=0
    evaluated_candidate_rows=0
    seed_eval_examples=[]

    for y in t["snapshots"]:
        x=by_turn.get(y["turn"])
        if not x:
            continue
        if y.get("candidate_evaluation_present"):
            treatment_eval_turns+=1
            ev=y.get("candidate_evaluation") or {}
            rows=list(ev.get("candidate_evaluations",[]) or [])
            evaluated_candidate_rows+=len(rows)
            if len(seed_eval_examples)<8:
                for row in rows:
                    cand=row.get("candidate")
                    if isinstance(cand,list) and cand and cand[0]=="BUY_SEED":
                        seed_eval_examples.append({
                            "turn":y["turn"],
                            "day":y["day"],
                            "candidate":cand,
                            "future_fixation":row.get("future_fixation"),
                            "reversibility":row.get("reversibility"),
                            "option_retention":row.get("option_retention"),
                        })
                        if len(seed_eval_examples)>=8:
                            break

        if x.get("candidate_evaluation")!=y.get("candidate_evaluation"):
            evaluation_changed+=1
        if x.get("candidate_ranking")!=y.get("candidate_ranking"):
            ranking_changed+=1
        if x.get("targets")!=y.get("targets") or x.get("best_crop")!=y.get("best_crop"):
            target_changed+=1
        if x.get("market")!=y.get("market") or x.get("final_action")!=y.get("final_action"):
            action_changed+=1

    payload={
        "schema":"kaggriculture.model-candidate-evaluation.v0",
        "seed":SEED,
        "seat":SEAT,
        "treatment_evaluation_received_turns":treatment_eval_turns,
        "evaluated_candidate_rows":evaluated_candidate_rows,
        "candidate_evaluation_changed_turns":evaluation_changed,
        "candidate_ranking_changed_turns":ranking_changed,
        "target_changed_turns":target_changed,
        "action_changed_turns":action_changed,
        "terminal_self_diff":t["self"]-c["self"],
        "terminal_margin_diff":t["margin"]-c["margin"],
        "seed_evaluation_examples":seed_eval_examples,
        "boundary":[
            "Flow-chan provides abstraction and Evaluation Lens only.",
            "Treatment adds model-side descriptive candidate evaluation.",
            "Evaluation preserves unknowns and does not emit score, rank, selection, or action.",
            "No action or terminal change is expected at this stage.",
            "A changed evaluation is evidence of bridge reachability, not proof that the model semantically understood the abstraction."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MODEL_CANDIDATE_EVALUATION_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
