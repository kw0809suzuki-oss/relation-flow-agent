#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"coarse_transition_effect_trace_v0_{SEED}.json")

def configure(mode):
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]=mode
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def snaps(trace):
    return ((((trace or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def play(mode):
    configure(mode)
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=combat.agent; env.run(players)
    rewards=[float(s.reward) for s in env.state]
    rows=[]
    prev_choice=None; prev_regime=None
    for s in snaps(combat.get_trace()):
        if int(s.get("day",0) or 0)<14: continue
        i=dict(s.get("origin_internal",{}) or {})
        row={
          "turn":s.get("turn"),"day":s.get("day"),"remaining":s.get("remaining"),
          "money":s.get("money"),"cows":s.get("cows"),"wheat":s.get("wheat"),
          "feed_need":s.get("feed_need"),
          "choice":i.get("model_guidance_choice"),
          "reason":i.get("model_guidance_reason"),
          "regime":i.get("coarse_regime"),
          "boundary_changed":bool(i.get("coarse_boundary_changed",False)),
          "choice_transition": prev_choice is not None and i.get("model_guidance_choice")!=prev_choice,
          "regime_transition": prev_regime is not None and i.get("coarse_regime")!=prev_regime,
          "action":s.get("action"),
        }
        rows.append(row)
        prev_choice=row["choice"]; prev_regime=row["regime"]
    return {"self":rewards[SEAT],"margin":rewards[SEAT]-rewards[1-SEAT],"rows":rows}

def main():
    current=play("objective_pressure_guidance")
    coarse=play("coarse_boundary_guidance")
    a={r["turn"]:r for r in current["rows"]}; b={r["turn"]:r for r in coarse["rows"]}
    common=sorted(set(a)&set(b))
    action_diffs=[t for t in common if a[t]["action"]!=b[t]["action"]]
    transitions=[r for r in coarse["rows"] if r["choice_transition"] or r["regime_transition"] or r["boundary_changed"]]
    near=[]
    for tr in transitions:
        t=tr["turn"]
        diffs=[d for d in action_diffs if abs(d-t)<=3]
        if diffs:
            near.append({
              "transition_turn":t,
              "day":tr["day"],
              "choice":tr["choice"],
              "regime":tr["regime"],
              "reason":tr["reason"],
              "nearby_action_diff_turns":diffs,
              "current_at_transition":a.get(t),
              "coarse_at_transition":tr
            })
    first_diff=action_diffs[0] if action_diffs else None
    payload={
      "schema":"kaggriculture.coarse-transition-effect-trace.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{
        "current_self":current["self"],"coarse_self":coarse["self"],
        "self_diff":coarse["self"]-current["self"],
        "current_margin":current["margin"],"coarse_margin":coarse["margin"],
        "margin_diff":coarse["margin"]-current["margin"]
      },
      "first_action_divergence":{
        "turn":first_diff,
        "current":a.get(first_diff) if first_diff is not None else None,
        "coarse":b.get(first_diff) if first_diff is not None else None
      },
      "candidate_transition_count":len(transitions),
      "action_divergence_count":len(action_diffs),
      "transitions_with_nearby_action_divergence":near,
      "boundary":"Observer only. Temporal adjacency does not establish causation."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self_diff":payload["terminal"]["self_diff"],"transitions":len(transitions),"action_diffs":len(action_diffs),"near":len(near)},ensure_ascii=False))

if __name__=="__main__": main()
