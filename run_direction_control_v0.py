#!/usr/bin/env python3
"""Direction Control v0.

Three-way paired Battle from the same deterministic seed/seat runtime:
C0: no direction
C1: selected direction, one +1 occupancy-budget rotation at the first comparable entry
C2: alternative nondominated-frontier direction, same +1 rotation at that same entry

"Alternative" is explicitly not a runner-up or second-best candidate.
"""

import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"direction_control_v0_{SEED}.json")

def configure(mode):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    os.environ["OUTER_MEANING_OPTION_PRESERVATION_DAY"]="14"
    os.environ["ORIGIN_EVALUATION_LENS"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_EVALUATION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_COMPARISON"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_SELECTION"]="1"
    os.environ["ORIGIN_MODEL_CANDIDATE_DIRECTION"]="1"
    os.environ["ORIGIN_MODEL_SELECTION_GUIDED_GENERATION"]="0"
    os.environ["ORIGIN_MODEL_SELECTION_TO_ACTION"]="0"
    os.environ["ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]=mode
    combat.set_probe_enabled(True)
    combat.set_attribution_enabled(True)
    combat.reset_telemetry()

def snapshots(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode):
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
        applied=dict(s.get("applied_origin_integration",{}) or {})
        internal=dict(s.get("origin_internal",{}) or {})
        out.append({
            "turn":s.get("turn"),
            "day":s.get("day"),
            "money":s.get("money"),
            "land":s.get("land"),
            "units":s.get("units"),
            "shed_sig":s.get("shed_sig"),
            "inv_sig":s.get("inv_sig"),
            "tile_sig":s.get("tile_sig"),
            "action":s.get("action"),
            "comparable_entry":bool(s.get("direction_control_comparable_entry",False)),
            "direction_state_delta_applied":bool(s.get("direction_state_delta_applied",False)),
            "selected_direction":s.get("selected_candidate_direction") or applied.get("candidate_direction"),
            "alternative_direction":s.get("alternative_candidate_direction") or applied.get("candidate_alternative_direction"),
            "selected_candidate":applied.get("candidate_selection"),
            "alternative_candidate":applied.get("candidate_alternative_frontier"),
            "native_targets":internal.get("native_targets_before_direction"),
            "targets_after":internal.get("direction_targets_after"),
        })
    return {
        "mode":mode,
        "self":rewards[SEAT],
        "opponent":rewards[1-SEAT],
        "margin":rewards[SEAT]-rewards[1-SEAT],
        "snapshots":out,
    }

def first_entry(run):
    for s in run["snapshots"]:
        if s.get("comparable_entry"):
            return s
    return None

def entry_signature(s):
    if not s:
        return None
    return {
        "turn":s.get("turn"), "day":s.get("day"), "money":s.get("money"),
        "land":s.get("land"), "units":s.get("units"),
        "shed_sig":s.get("shed_sig"), "inv_sig":s.get("inv_sig"), "tile_sig":s.get("tile_sig"),
        "selected_candidate":s.get("selected_candidate"),
        "alternative_candidate":s.get("alternative_candidate"),
    }

def sign(x):
    if x > 0: return "+"
    if x < 0: return "-"
    return "0"

def main():
    c0=play("none")
    c1=play("selected")
    c2=play("alternative")
    e0,e1,e2=first_entry(c0),first_entry(c1),first_entry(c2)

    sig0,sig1,sig2=entry_signature(e0),entry_signature(e1),entry_signature(e2)
    entry_aligned=bool(sig0 is not None and sig0==sig1==sig2)

    selected_delta=c1["self"]-c0["self"]
    alternative_delta=c2["self"]-c0["self"]

    control_by_turn={s["turn"]:s for s in c0["snapshots"]}
    def propagation(run, entry):
        if not entry: return 0
        t0=entry["turn"]
        return sum(
            1 for s in run["snapshots"]
            if s["turn"]>=t0
            and s["turn"] in control_by_turn
            and s.get("action") != control_by_turn[s["turn"]].get("action")
        )

    comparable=bool(e0 and e1 and e2)
    selected_state_delta=bool(e1 and e1.get("direction_state_delta_applied"))
    alternative_state_delta=bool(e2 and e2.get("direction_state_delta_applied"))
    selected_first_action_delta=bool(e1 and e0 and e1.get("action")!=e0.get("action"))
    alternative_first_action_delta=bool(e2 and e0 and e2.get("action")!=e0.get("action"))

    classification="not_comparable"
    if comparable and entry_aligned:
        sgn,agn=sign(selected_delta),sign(alternative_delta)
        classification=f"S{sgn}/A{agn}"
        if not selected_state_delta or not alternative_state_delta:
            classification="application_failure"
        elif not selected_first_action_delta and not alternative_first_action_delta:
            classification="actionability_not_reached_at_entry"

    payload={
        "schema":"kaggriculture.direction-control.v0",
        "seed":SEED,"seat":SEAT,
        "entry_comparable":comparable,
        "entry_aligned":entry_aligned,
        "entry_signature":sig0,
        "selected_direction":e1.get("selected_direction") if e1 else None,
        "alternative_frontier_direction":e2.get("alternative_direction") if e2 else None,
        "control_terminal_self":c0["self"],
        "selected_terminal_self":c1["self"],
        "alternative_terminal_self":c2["self"],
        "selected_terminal_self_delta_vs_control":selected_delta,
        "alternative_terminal_self_delta_vs_control":alternative_delta,
        "selected_minus_alternative_terminal_self":c1["self"]-c2["self"],
        "selected_terminal_margin_delta_vs_control":c1["margin"]-c0["margin"],
        "alternative_terminal_margin_delta_vs_control":c2["margin"]-c0["margin"],
        "selected_state_delta_applied":selected_state_delta,
        "alternative_state_delta_applied":alternative_state_delta,
        "selected_first_action_delta":selected_first_action_delta,
        "alternative_first_action_delta":alternative_first_action_delta,
        "selected_propagation_action_delta_turns":propagation(c1,e1),
        "alternative_propagation_action_delta_turns":propagation(c2,e2),
        "classification":classification,
        "boundary":[
            "Alternative frontier candidate is not a runner-up or second-best.",
            "The three runs must match at the first comparable pre-direction entry before directional effects are interpreted.",
            "Only one +1 occupancy-budget direction intervention is attempted per treatment run.",
            "Selection quality is not inferred from a single case.",
            "Direction Control asks whether selected direction carries terminal-sign information relative to an unranked alternative frontier direction."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print("DIRECTION_CONTROL_RESULT "+json.dumps(payload,ensure_ascii=False,separators=(",",":"),default=str))

if __name__=="__main__":
    main()
