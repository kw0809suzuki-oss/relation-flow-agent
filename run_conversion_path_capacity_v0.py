#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"conversion_path_capacity_v0_{SEED}.json")
MODES=["throughput_match","throughput_with_slack","conversion_window_fit"]

def configure(mode=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ.pop("OUTER_MEANING_OPTION_PRESERVATION_DAY",None)
    os.environ.pop("OUTER_MEANING_REALIZABLE_CAPACITY_DAY",None)
    os.environ["OUTER_MEANING_CONVERSION_PATH_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1" if mode else "0"
    os.environ["ORIGIN_CONVERSION_PATH_HYPOTHESIS"]=mode or "none"
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode=None):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent; env.run(players)
    rewards=[float(s.reward) for s in env.state]
    ss=[s for s in snapshots(combat.get_trace()) if int(s.get("day",0) or 0)>=14]
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"snapshots":ss}

def compare(control,treat,mode):
    cb={x["turn"]:x for x in control["snapshots"]}
    changed=[]
    for y in treat["snapshots"]:
        x=cb.get(y["turn"])
        if x is not None and x.get("action")!=y.get("action"):
            if len(changed)<6: changed.append({"turn":y["turn"],"day":y["day"],"control":x.get("action"),"treatment":y.get("action")})
    return {
        "hypothesis":mode,
        "action_changed_turns":sum(1 for y in treat["snapshots"] if y["turn"] in cb and cb[y["turn"]].get("action")!=y.get("action")),
        "terminal_self_diff":treat["self"]-control["self"],
        "terminal_margin_diff":treat["margin"]-control["margin"],
        "examples":changed
    }

def main():
    control=play()
    hypotheses={m:compare(control,play(m),m) for m in MODES}
    payload={
      "schema":"kaggriculture.conversion-path-capacity.v0","seed":SEED,"seat":SEAT,
      "control_self":control["self"],"control_margin":control["margin"],
      "hypotheses":hypotheses,
      "boundary":[
        "Flow-chan supplies the abstract direction only.",
        "Hypotheses are model-side operationalizations, not rules.",
        "Battle differences are evidence.",
        "Re-abstraction is generated from differences and remains a hypothesis."
      ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__": main()
