#!/usr/bin/env python3
import json, os
from collections import Counter
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"flowchan_guidance_autonomy_v0_{SEED}.json")

def configure(mode=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_GUIDED_CONVERSION_DAY"]="14"

    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"

    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1" if mode else "0"
    os.environ["ORIGIN_GUIDANCE_MODE"]=mode or "none"

    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode=None):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent; env.run(players)
    rewards=[float(s.reward) for s in env.state]
    ss=[]
    for s in snapshots(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        internal=dict(s.get("origin_internal",{}) or {})
        ss.append({
            "turn":s.get("turn"),"day":s.get("day"),"action":s.get("action"),
            "choice":internal.get("model_guidance_choice"),
            "reason":internal.get("model_guidance_reason"),
        })
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"snapshots":ss}

def compare(control,treat,label):
    cb={x["turn"]:x for x in control["snapshots"]}
    changed=sum(1 for y in treat["snapshots"] if y["turn"] in cb and cb[y["turn"]].get("action")!=y.get("action"))
    choices=Counter(str(y.get("choice") or "none") for y in treat["snapshots"])
    reasons=Counter(str(y.get("reason") or "none") for y in treat["snapshots"])
    return {
        "arm":label,
        "action_changed_turns":changed,
        "terminal_self_diff":treat["self"]-control["self"],
        "terminal_margin_diff":treat["margin"]-control["margin"],
        "model_choice_counts":dict(choices),
        "model_reason_counts":dict(reasons),
    }

def main():
    control=play(None)
    fixed=play("throughput_match")
    guided=play("guided_autonomy")
    payload={
      "schema":"kaggriculture.flowchan-guidance-autonomy.v0",
      "seed":SEED,"seat":SEAT,
      "control_self":control["self"],"control_margin":control["margin"],
      "fixed_match":compare(control,fixed,"fixed_match"),
      "guided_autonomy":compare(control,guided,"guided_autonomy"),
      "boundary":[
        "Flow-chan guidance is explicitly non-binding.",
        "guided_autonomy is a scripted model-side proxy, not proof of free-form reasoning.",
        "Battle returns differences only; no automatic winner or rule adoption.",
        "The abstraction remains a hypothesis."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
