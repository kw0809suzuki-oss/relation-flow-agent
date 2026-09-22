#!/usr/bin/env python3
"""Model Candidate Comparison Probe v0.

A/B:
- Control: Abstraction + Lens + Candidate Evaluation.
- Treatment: same + model-side partial-order Candidate Comparison.

No total ranking, selection, target rewrite, action rewrite, scalar score, or weights.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"model_candidate_comparison_v0_{SEED}.json")

def configure(compare=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    os.environ["ORIGIN_EVALUATION_LENS"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"]="1" if compare else "0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(compare=False):
    configure(compare)
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
        comp=integ.get("candidate_comparison")
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "targets":internal.get("targets"),
            "best_crop":internal.get("best_crop"),
            "market":internal.get("market"),
            "final_action":s.get("action"),
            "candidate_comparison_present":bool(integ.get("candidate_comparison_present")),
            "candidate_comparison":comp,
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
    comparison_changed=0
    ranking_changed=0
    target_changed=0
    action_changed=0
    compare_turns=0
    pair_count=0
    relation_counts={}
    frontier_examples=[]

    for y in t["snapshots"]:
        x=by_turn.get(y["turn"])
        if not x:
            continue
        comp=y.get("candidate_comparison")
        if y.get("candidate_comparison_present"):
            compare_turns+=1
            pairs=list((comp or {}).get("pairwise_relations",[]) or [])
            pair_count+=len(pairs)
            for p in pairs:
                rel=p.get("relation")
                relation_counts[rel]=relation_counts.get(rel,0)+1
            if len(frontier_examples)<8:
                frontier_examples.append({
                    "turn":y["turn"],
                    "day":y["day"],
                    "frontier":(comp or {}).get("nondominated_frontier"),
                    "pair_count":len(pairs),
                })

        if x.get("candidate_comparison")!=y.get("candidate_comparison"):
            comparison_changed+=1
        if x.get("candidate_ranking")!=y.get("candidate_ranking"):
            ranking_changed+=1
        if x.get("targets")!=y.get("targets") or x.get("best_crop")!=y.get("best_crop"):
            target_changed+=1
        if x.get("market")!=y.get("market") or x.get("final_action")!=y.get("final_action"):
            action_changed+=1

    payload={
        "schema":"kaggriculture.model-candidate-comparison.v0",
        "seed":SEED,
        "seat":SEAT,
        "comparison_received_turns":compare_turns,
        "candidate_comparison_changed_turns":comparison_changed,
        "pairwise_relation_count":pair_count,
        "relation_counts":relation_counts,
        "candidate_ranking_changed_turns":ranking_changed,
        "target_changed_turns":target_changed,
        "action_changed_turns":action_changed,
        "terminal_self_diff":t["self"]-c["self"],
        "terminal_margin_diff":t["margin"]-c["margin"],
        "frontier_examples":frontier_examples,
        "boundary":[
            "Flow-chan still provides only abstraction and lens.",
            "Treatment adds model-side partial-order comparison over descriptive evaluations.",
            "No scalar score, fixed weights, total ranking, selection, target rewrite, or action rewrite.",
            "Unknown or conflicting dimensions remain unresolved.",
            "Comparison change demonstrates comparison-path reachability only; it is not evidence that the abstraction improves play."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MODEL_CANDIDATE_COMPARISON_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
