#!/usr/bin/env python3
"""Internal Representation Audit v0.

Observation-only replay of the same Fresh10.
Captures the actual Strong Origin internal trace at Day4 h10 without changing
the returned action. Also records the public-rule reachable-future shadow for
the already-certified existing MELON seed opportunity.

No Candidate, Direction, score, or policy mutation.
"""
import copy,json,os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"internal_representation_audit_v0_{SEED}.json")


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def main():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()

    captured={}

    def observed(obs):
        action=body_only.agent(obs)
        if int(obs.get("day",-1))==4 and int(obs.get("hour",-1))==10 and not captured:
            me=obs["farms"][obs["player"]]
            private=obs.get("private",{}) or {}
            trace=body_only.body.get_last_trace()
            internal=copy.deepcopy(trace.get("internal",{}))
            captured.update({
                "day":4,"hour":10,
                "cash":float(me.get("money",0) or 0),
                "seeds":copy.deepcopy(private.get("seeds",{})),
                "farmer":copy.deepcopy(me.get("farmer")),
                "hands":copy.deepcopy(me.get("hands",[])),
                "base_action":copy.deepcopy(trace.get("base_action",{})),
                "final_action":copy.deepcopy(trace.get("final_action",{})),
                "overlay_changed_farmer":bool(trace.get("overlay_changed_farmer")),
                "overlay_changed_hands":bool(trace.get("overlay_changed_hands")),
                "overlay_changed_market":bool(trace.get("overlay_changed_market")),
                "internal":internal,
                "shadow_world_reachable":{
                    "asset":"MELON",
                    "existing_seed_available":int((private.get("seeds",{}) or {}).get("MELON",0) or 0),
                    "if_entered_day":4,
                    "next_production_day":10,
                    "harvest_eligible_day":14,
                    "inside_day8_to_12_production_window":True,
                    "inside_day8_to_12_harvest_window":False,
                },
            })
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[basecfg.OPPONENT,basecfg.OPPONENT]
    players[SEAT]=observed
    env.run(players)
    if not captured:
        raise SystemExit("Day4 h10 capture missing")

    payload={
        "schema":"kaggriculture.strong-origin-v2.internal-representation-audit.v0",
        "seed":SEED,"seat":SEAT,
        "capture":captured,
        "policy_mutated":False,
        "boundary":[
            "The shadow reachable future is computed for logging only and does not modify the returned action.",
            "The audit does not infer meaning from absent variable names alone; static decision-path analysis is aggregated separately.",
            "No Candidate, Direction, or policy mutation."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("INTERNAL_REPRESENTATION_AUDIT "+json.dumps({
        "seed":SEED,
        "strategy":captured["internal"].get("strategy_name"),
        "targets":captured["internal"].get("targets"),
        "best_crop":captured["internal"].get("best_crop"),
        "scores":captured["internal"].get("scores"),
        "base_action":captured["base_action"],
        "final_action":captured["final_action"],
        "shadow":captured["shadow_world_reachable"],
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
