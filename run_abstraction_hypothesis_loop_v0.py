#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"abstraction_hypothesis_loop_v0_{SEED}.json")
MODES=["seed_surface","hire_workload","land_activation"]

def configure(mode=None):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ.pop("OUTER_MEANING_OPTION_PRESERVATION_DAY",None)
    os.environ["OUTER_MEANING_REALIZABLE_CAPACITY_DAY"]="14"

    # Keep previous hand-built reasoning chain off.
    for k in [
        "ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION",
        "ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION",
        "ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION",
        "ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"
    ]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"

    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1" if mode else "0"
    os.environ["ORIGIN_COMMITMENT_HYPOTHESIS"]=mode or "none"

    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode=None):
    configure(mode)
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
            "received":bool(internal.get("realizable_received",False)),
            "hypothesis_mode":internal.get("hypothesis_mode"),
            "seed_budget":internal.get("seed_realizable_budget_remaining"),
            "native_desired_units":internal.get("native_desired_units"),
            "realizable_units":internal.get("realizable_units"),
            "land_activation_capacity":internal.get("land_activation_capacity"),
            "land_realizable_ok":internal.get("land_realizable_ok"),
        })
    return {
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "snapshots":out
    }

def summarize(control,treatment,mode):
    cb={x["turn"]:x for x in control["snapshots"]}
    changed=[]
    for y in treatment["snapshots"]:
        x=cb.get(y["turn"])
        if x is not None and x.get("action")!=y.get("action"):
            if len(changed)<8:
                changed.append({
                    "turn":y["turn"],"day":y["day"],
                    "control":x.get("action"),"treatment":y.get("action")
                })
    return {
        "hypothesis":mode,
        "received_turns":sum(1 for x in treatment["snapshots"] if x.get("received")),
        "action_changed_turns":sum(
            1 for y in treatment["snapshots"]
            if y["turn"] in cb and cb[y["turn"]].get("action")!=y.get("action")
        ),
        "terminal_self_diff":treatment["self"]-control["self"],
        "terminal_margin_diff":treatment["margin"]-control["margin"],
        "examples":changed
    }

def main():
    control=play(None)
    hypotheses={}
    for mode in MODES:
        hypotheses[mode]=summarize(control,play(mode),mode)
    payload={
        "schema":"kaggriculture.abstraction-hypothesis-loop.v0",
        "seed":SEED,"seat":SEAT,
        "control_self":control["self"],
        "control_margin":control["margin"],
        "hypotheses":hypotheses,
        "boundary":[
            "Flow-chan provides the abstract direction only.",
            "Model-side adapters discover and operationalize commitment hypotheses.",
            "No winner or rule is adopted automatically.",
            "Battle differences are evidence; the abstraction remains a hypothesis."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print("ABSTRACTION_HYPOTHESIS_LOOP_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str))

if __name__=="__main__":
    main()
