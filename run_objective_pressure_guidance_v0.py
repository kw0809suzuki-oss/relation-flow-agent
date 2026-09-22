#!/usr/bin/env python3
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"objective_pressure_guidance_v0_{SEED}.json")

def configure(mode=None, packet="pressure"):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY","OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]:
        os.environ.pop(k,None)
    if packet=="pressure":
        os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    else:
        os.environ["OUTER_MEANING_GUIDED_CONVERSION_DAY"]="14"

    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1" if mode else "0"
    os.environ["ORIGIN_GUIDANCE_MODE"]=mode or "none"
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode=None, packet="pressure"):
    configure(mode,packet)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent; env.run(players)
    rewards=[float(s.reward) for s in env.state]
    ss=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        internal=dict(s.get("origin_internal",{}) or {})
        ss.append({
            "turn":s.get("turn"),"action":s.get("action"),
            "choice":internal.get("model_guidance_choice"),
            "reason":internal.get("model_guidance_reason"),
        })
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"snapshots":ss}

def compare(control,treat,label):
    cb={x["turn"]:x for x in control["snapshots"]}
    choices=Counter(str(x.get("choice") or "none") for x in treat["snapshots"])
    reasons=Counter(str(x.get("reason") or "none") for x in treat["snapshots"])
    return {
        "arm":label,
        "action_changed_turns":sum(1 for y in treat["snapshots"] if y["turn"] in cb and cb[y["turn"]].get("action")!=y.get("action")),
        "terminal_self_diff":treat["self"]-control["self"],
        "terminal_margin_diff":treat["margin"]-control["margin"],
        "choice_counts":dict(choices),
        "reason_counts":dict(reasons),
    }

def main():
    control=play(None,"pressure")
    fixed=play("throughput_match","pressure")
    previous_guided=play("guided_autonomy","guided")
    pressure=play("objective_pressure_guidance","pressure")
    payload={
        "schema":"kaggriculture.objective-pressure-guidance.v0",
        "seed":SEED,"seat":SEAT,
        "control_self":control["self"],"control_margin":control["margin"],
        "fixed_match":compare(control,fixed,"fixed_match"),
        "previous_guided":compare(control,previous_guided,"previous_guided"),
        "objective_pressure":compare(control,pressure,"objective_pressure"),
        "boundary":[
            "Flow-chan frames a tension; it does not choose the objective.",
            "The model-side chooser is a scripted proxy, not proof of free-form autonomy.",
            "Battle returns observed differences only.",
            "All abstractions remain hypotheses."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
