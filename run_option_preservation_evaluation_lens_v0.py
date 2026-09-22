#!/usr/bin/env python3
"""Option Preservation Evaluation Lens Probe v0.

A/B:
- Baseline: OPTION_PRESERVATION abstraction only.
- Lens: same abstraction + Evaluation Lens questions attached to native candidates.

No evaluation answer, score, ranking, target rewrite, action rewrite, threshold,
cap, or suppression is allowed.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"option_preservation_evaluation_lens_v0_{SEED}.json")

def configure(lens=False):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    if lens:
        os.environ["ORIGIN_EVALUATION_LENS"]="1"
    else:
        os.environ["ORIGIN_EVALUATION_LENS"]="0"
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(lens=False):
    configure(lens)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]
    players[SEAT]=combat.agent
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    out=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        internal=dict(s.get("origin_internal",{}) or {})
        integ=dict(s.get("origin_integration_current",{}) or {})
        lens_obj=integ.get("evaluation_lens")
        out.append({
            "turn":s.get("turn"),"day":s.get("day"),
            "strategy":internal.get("strategy_name"),
            "targets":internal.get("targets"),
            "scores":internal.get("scores"),
            "best_crop":internal.get("best_crop"),
            "market":internal.get("market"),
            "final_action":s.get("action"),
            "lens_present":bool(integ.get("evaluation_lens_present")),
            "lens_candidate_count":len((lens_obj or {}).get("candidates",[]) or []),
            "candidate_evaluation":integ.get("candidate_evaluation"),
            "candidate_ranking":integ.get("candidate_ranking"),
        })
    return {"self":rewards[SEAT],"opponent":rewards[1-SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"snapshots":out}

def main():
    b=play(False)
    l=play(True)
    by_turn={x["turn"]:x for x in b["snapshots"]}
    rep=rank=target=action=0
    lens_turns=0
    examples=[]
    for y in l["snapshots"]:
        x=by_turn.get(y["turn"])
        if not x: continue
        if y.get("lens_present"):
            lens_turns+=1
            if len(examples)<5:
                examples.append({"turn":y["turn"],"day":y["day"],"candidate_count":y["lens_candidate_count"]})
        if x.get("lens_present")!=y.get("lens_present") or x.get("lens_candidate_count")!=y.get("lens_candidate_count"):
            rep+=1
        if x.get("candidate_ranking")!=y.get("candidate_ranking"):
            rank+=1
        if x.get("targets")!=y.get("targets") or x.get("best_crop")!=y.get("best_crop"):
            target+=1
        if x.get("market")!=y.get("market") or x.get("final_action")!=y.get("final_action"):
            action+=1
    payload={
        "schema":"kaggriculture.option-preservation-evaluation-lens.v0",
        "seed":SEED,"seat":SEAT,
        "lens_received_turns":lens_turns,
        "candidate_representation_changed_turns":rep,
        "candidate_ranking_changed_turns":rank,
        "target_changed_turns":target,
        "action_changed_turns":action,
        "terminal_self_diff":l["self"]-b["self"],
        "terminal_margin_diff":l["margin"]-b["margin"],
        "lens_examples":examples,
        "boundary":[
            "Baseline and Lens both receive OPTION_PRESERVATION abstraction.",
            "Lens adds only three evaluation questions to existing native candidates.",
            "No candidate evaluation answer, score, ranking, threshold, target rewrite, or action rewrite is produced.",
            "Representation change without ranking/action change is the expected signature of Abstraction -> Evaluation Lens only."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("OPTION_PRESERVATION_EVALUATION_LENS_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
